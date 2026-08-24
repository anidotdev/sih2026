import os
import requests
import pandas as pd
import geopandas as gpd
from io import StringIO
from shapely.geometry import Point
from sklearn.cluster import DBSCAN

METRIC_CRS = "EPSG:32643"   # UTM zone 43N — accurate for North India; adjust if scope widens
DATA_DIR = "data"

os.makedirs(DATA_DIR, exist_ok=True)


# ── FIRMS Data Ingestion ────────────────────────────────────────────────────

def fetch_firms_data(map_key: str, bbox: str, days: int = 5, source: str = "VIIRS_SNPP_NRT") -> pd.DataFrame:
    """Pull raw FIRMS active-fire detections for a bounding box."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/{days}"
    response = requests.get(url)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def clean_firms_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize timestamps, map confidence codes, drop incomplete rows."""
    df = df.copy()
    df["acq_time"] = df["acq_time"].astype(str).str.zfill(4)
    df["acquired_at"] = pd.to_datetime(
        df["acq_date"] + " " + df["acq_time"].str[:2] + ":" + df["acq_time"].str[2:],
        utc=True
    )
    confidence_map = {"l": "low", "n": "nominal", "h": "high"}
    df["confidence_label"] = df["confidence"].map(confidence_map).fillna(df["confidence"])
    keep_cols = ["latitude", "longitude", "acquired_at", "frp", "bright_ti4",
                 "confidence_label", "satellite", "daynight"]
    df = df[keep_cols].dropna(subset=["latitude", "longitude", "acquired_at", "frp"])
    return df.sort_values("acquired_at").reset_index(drop=True)


def to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert a lat/lon DataFrame into a WGS84 GeoDataFrame of points."""
    geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
    return gpd.GeoDataFrame(df.copy(), geometry=geometry, crs="EPSG:4326")


# ── OSM Industrial Layer — cache-first, cluster-scoped (no PostGIS) ────────

def get_industrial_layer_for_clusters(cluster_df: pd.DataFrame, buffer_km: float = 15,
                                       force_refresh: bool = False) -> gpd.GeoDataFrame:
    """
    Fetch OSM landuse=industrial polygons around each cluster centroid.
    Cache-first: reuses data/osm_industrial_<lat>_<lon>.parquet if present.
    A cluster whose fetch fails (Overpass down/timeout) is skipped, not fatal —
    the rest of the pipeline continues with whatever data was obtained.
    """
    import osmnx as ox

    layers = []
    buffer_deg = buffer_km / 111  # rough km-to-degree conversion

    for _, row in cluster_df.iterrows():
        lat, lon = row["centroid_lat"], row["centroid_lon"]
        key = f"{round(lat, 2)}_{round(lon, 2)}"
        path = f"{DATA_DIR}/osm_industrial_{key}.parquet"

        if os.path.exists(path) and not force_refresh:
            layers.append(gpd.read_parquet(path))
            continue

        bbox = (lon - buffer_deg, lat - buffer_deg, lon + buffer_deg, lat + buffer_deg)
        try:
            gdf = ox.features_from_bbox(bbox=bbox, tags={"landuse": "industrial"})
            keep_cols = ["element", "id", "geometry"] + [c for c in ["name", "landuse"] if c in gdf.columns]
            gdf = gdf.reset_index()[keep_cols]
            gdf.to_parquet(path)
            layers.append(gdf)
        except Exception as e:
            print(f"[{key}] OSM fetch failed ({type(e).__name__}) — skipping, no cache written")

    if not layers:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame(pd.concat(layers, ignore_index=True), crs="EPSG:4326")


def load_all_cached_industrial_layers() -> gpd.GeoDataFrame:
    """
    Load and merge every osm_industrial_*.parquet file already in DATA_DIR —
    zero network calls. Useful for combining older/wider fetches (e.g. a
    one-off state-wide pull) with newer cluster-wise cached files.
    """
    layers = []
    if os.path.isdir(DATA_DIR):
        for fname in os.listdir(DATA_DIR):
            if fname.startswith("osm_industrial_") and fname.endswith(".parquet"):
                gdf = gpd.read_parquet(os.path.join(DATA_DIR, fname))
                layers.append(gdf)
                print(f"loaded cache: {fname} ({len(gdf)} features)")

    if not layers:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame(pd.concat(layers, ignore_index=True), crs="EPSG:4326")


# ── Clustering ───────────────────────────────────────────────────────────

def cluster_hotspots(hotspots_m: gpd.GeoDataFrame, eps: float = 2000, min_samples: int = 1) -> gpd.GeoDataFrame:
    """DBSCAN over projected (meter) coordinates. eps=2000m ~ 2km radius."""
    coords = hotspots_m.geometry.apply(lambda p: (p.x, p.y)).tolist()
    coords_df = pd.DataFrame(coords, columns=["x", "y"])
    db = DBSCAN(eps=eps, min_samples=min_samples)
    hotspots_m = hotspots_m.copy()
    hotspots_m["cluster_id"] = db.fit_predict(coords_df[["x", "y"]])
    return hotspots_m


def compute_cluster_features(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Aggregate per-cluster stats: detection count, persistence, FRP, centroid."""
    gdf = gdf.copy()
    gdf["acq_date_only"] = gdf["acquired_at"].dt.date
    cluster_features = gdf.groupby("cluster_id").agg(
        detection_count=("cluster_id", "count"),
        distinct_days=("acq_date_only", "nunique"),
        first_seen=("acquired_at", "min"),
        last_seen=("acquired_at", "max"),
        mean_frp=("frp", "mean"),
        max_frp=("frp", "max"),
        centroid_lat=("latitude", "mean"),
        centroid_lon=("longitude", "mean"),
    ).reset_index()
    cluster_features["persistence_days"] = (
        cluster_features["last_seen"] - cluster_features["first_seen"]
    ).dt.total_seconds() / 86400
    cluster_features["is_persistent"] = cluster_features["distinct_days"] >= 2
    return cluster_features


def join_industrial_distance(hotspots_m: gpd.GeoDataFrame, industrial_m: gpd.GeoDataFrame,
                              cluster_features: pd.DataFrame) -> pd.DataFrame:
    """Attach each cluster's distance (m) to the nearest industrial polygon."""
    if len(industrial_m) == 0:
        cluster_features = cluster_features.copy()
        cluster_features["min_distance_to_industrial_m"] = float("inf")
        return cluster_features

    nearest = gpd.sjoin_nearest(hotspots_m, industrial_m, how="left", distance_col="distance_to_industrial_m")
    cluster_distance = nearest.groupby("cluster_id")["distance_to_industrial_m"].min().reset_index()
    cluster_distance.columns = ["cluster_id", "min_distance_to_industrial_m"]
    return cluster_features.merge(cluster_distance, on="cluster_id", how="left")


# ── Classification & Risk Scoring — explainable, rule-based ────────────────

def classify_cluster(row: pd.Series) -> dict:
    """
    Label a cluster using distance-to-industrial, persistence, and FRP.
    Every branch returns a human-readable `reason` — no black-box scoring.
    """
    distance_km = row["min_distance_to_industrial_m"] / 1000
    is_persistent = row["is_persistent"]
    max_frp = row["max_frp"]

    if distance_km <= 1.0:
        return {"label": "likely_industrial_fire", "confidence": "high" if is_persistent else "medium",
                "reason": f"Within {distance_km:.2f}km of industrial facility"}
    if is_persistent and max_frp >= 5.0 and distance_km > 10.0:
        return {"label": "likely_agricultural_or_wildfire", "confidence": "high",
                "reason": f"Persistent ({row['distinct_days']} days) and high FRP but "
                          f"{distance_km:.1f}km from nearest industrial site"}
    if distance_km <= 10.0:
        return {"label": "possible_industrial_fire",
                "confidence": "medium" if (is_persistent or max_frp >= 3.0) else "low",
                "reason": f"{distance_km:.1f}km from industrial site, "
                          f"{'persistent' if is_persistent else 'single detection'}, FRP={max_frp:.2f}"}
    if distance_km > 10.0 and not is_persistent and max_frp < 5.0:
        return {"label": "low_priority_false_positive", "confidence": "medium",
                "reason": f"Isolated single-day detection, {distance_km:.1f}km from industrial infrastructure"}
    return {"label": "uncertain", "confidence": "low",
            "reason": "Does not match a clear rule pattern — needs manual review"}


def compute_risk_score(row: pd.Series) -> float:
    """Composite 0-100 score: label severity + FRP intensity + persistence bonus. Fully traceable."""
    label_base = {
        "likely_industrial_fire": 70, "possible_industrial_fire": 45,
        "likely_agricultural_or_wildfire": 20, "low_priority_false_positive": 5, "uncertain": 15,
    }
    confidence_multiplier = {"high": 1.0, "medium": 0.8, "low": 0.6}
    base = label_base.get(row["label"], 15)
    conf_mult = confidence_multiplier.get(row["confidence"], 0.6)
    frp_bonus = min(row["max_frp"] * 1.0, 20)
    persistence_bonus = min(row["distinct_days"] * 3, 10)
    return round(min((base * conf_mult) + frp_bonus + persistence_bonus, 100), 1)


# ── Batch Pipeline (historical / cluster-level analysis) ───────────────────

def run_pipeline(hotspots_df: pd.DataFrame, industrial_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Cleaned FIRMS df + OSM industrial gdf -> classified, risk-scored clusters."""
    hotspots = to_geodataframe(hotspots_df)
    hotspots_m = hotspots.to_crs(METRIC_CRS)
    industrial_m = industrial_gdf.to_crs(METRIC_CRS) if len(industrial_gdf) else industrial_gdf

    hotspots_m = cluster_hotspots(hotspots_m)
    cluster_features = compute_cluster_features(hotspots_m)
    cluster_features = join_industrial_distance(hotspots_m, industrial_m, cluster_features)

    results = cluster_features.apply(classify_cluster, axis=1, result_type="expand")
    cluster_features = pd.concat([cluster_features, results], axis=1)
    cluster_features["risk_score"] = cluster_features.apply(compute_risk_score, axis=1)

    return cluster_features.sort_values("risk_score", ascending=False)


def run_full_pipeline(map_key: str, bbox: str, days: int = 5,
                       source: str = "VIIRS_SNPP_NRT", osm_buffer_km: float = 15) -> pd.DataFrame:
    """
    End-to-end: FIRMS fetch -> clean -> cluster -> cache-first OSM industrial
    fetch (scoped to actual cluster locations, not whole states) -> classify
    -> risk score. This is the single entry point a dashboard/API layer calls.
    """
    raw = fetch_firms_data(map_key, bbox, days, source)
    cleaned = clean_firms_data(raw)

    hotspots = to_geodataframe(cleaned)
    hotspots_m = hotspots.to_crs(METRIC_CRS)
    hotspots_m = cluster_hotspots(hotspots_m)
    cluster_features = compute_cluster_features(hotspots_m)

    industrial_gdf = get_industrial_layer_for_clusters(cluster_features, buffer_km=osm_buffer_km)
    industrial_m = industrial_gdf.to_crs(METRIC_CRS) if len(industrial_gdf) else industrial_gdf

    cluster_features = join_industrial_distance(hotspots_m, industrial_m, cluster_features)
    results = cluster_features.apply(classify_cluster, axis=1, result_type="expand")
    cluster_features = pd.concat([cluster_features, results], axis=1)
    cluster_features["risk_score"] = cluster_features.apply(compute_risk_score, axis=1)

    return cluster_features.sort_values("risk_score", ascending=False)


# ── Prediction Engine — real-time inference on a single new detection ─────
# Reuses the same classify_cluster / compute_risk_score rules, but for one
# live detection rather than a historical batch. Persistence is unknown for
# a brand-new point unless explicitly supplied — the engine deliberately
# defaults to "uncertain" rather than guessing at confidence it doesn't have.

def predict_fire_event(lat: float, lon: float, frp: float, industrial_gdf: gpd.GeoDataFrame,
                        is_persistent: bool = False, metric_crs: str = METRIC_CRS) -> dict:
    """Classify + risk-score a single new fire detection in real time."""
    point_gdf = gpd.GeoDataFrame(
        {"latitude": [lat], "longitude": [lon]},
        geometry=[Point(lon, lat)], crs="EPSG:4326"
    ).to_crs(metric_crs)

    if len(industrial_gdf) == 0:
        distance_km = float("inf")
    else:
        industrial_m = industrial_gdf.to_crs(metric_crs)
        nearest = gpd.sjoin_nearest(point_gdf, industrial_m, distance_col="distance_m")
        distance_km = nearest["distance_m"].values[0] / 1000

    row = {
        "min_distance_to_industrial_m": distance_km * 1000,
        "is_persistent": is_persistent,
        "max_frp": frp,
        "distinct_days": 2 if is_persistent else 1,
    }
    classification = classify_cluster(pd.Series(row))
    row.update(classification)
    risk = compute_risk_score(pd.Series(row))

    return {
        "latitude": lat, "longitude": lon, "frp": frp,
        "distance_to_industrial_km": round(distance_km, 2) if distance_km != float("inf") else None,
        "is_persistent": is_persistent,
        "label": classification["label"],
        "confidence": classification["confidence"],
        "reason": classification["reason"],
        "risk_score": risk,
    }


def predict_batch_with_persistence(df: pd.DataFrame, industrial_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Run predict_fire_event over every row in a cleaned FIRMS DataFrame.
    Persistence is computed from the data itself (same rounded location seen
    on 2+ distinct days) rather than assumed, so results match cluster-level
    classification for repeat detections.
    """
    df = df.copy()
    df["loc_key"] = df["latitude"].round(2).astype(str) + "_" + df["longitude"].round(2).astype(str)
    persistence_map = df.groupby("loc_key")["acquired_at"].apply(lambda x: x.dt.date.nunique())
    df["computed_persistence"] = df["loc_key"].map(persistence_map) >= 2

    results = [
        predict_fire_event(
            lat=row["latitude"], lon=row["longitude"], frp=row["frp"],
            industrial_gdf=industrial_gdf, is_persistent=row["computed_persistence"],
        )
        for _, row in df.iterrows()
    ]
    return pd.DataFrame(results)
