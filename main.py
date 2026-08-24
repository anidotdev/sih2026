import os
import geopandas as gpd

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from shapely.geometry import mapping
from fastapi.middleware.cors import CORSMiddleware

from pipeline import fetch_firms_data, clean_firms_data, run_pipeline


# Load environment variables from .env
load_dotenv()

app = FastAPI(title="Industrial Fire Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Environment variables
MAP_KEY = os.getenv("FIRMS_MAP_KEY")
OSM_CACHE_PATH = os.getenv(
    "OSM_CACHE_PATH",
    "data/osm_industrial_ncr_haryana.parquet"
)


# Load OSM reference data once at startup
industrial_gdf = None


@app.on_event("startup")
def load_reference_data():
    global industrial_gdf

    if not MAP_KEY:
        raise RuntimeError("FIRMS_MAP_KEY is not configured")

    if not os.path.exists(OSM_CACHE_PATH):
        raise RuntimeError(f"OSM cache not found at {OSM_CACHE_PATH}")

    industrial_gdf = gpd.read_parquet(OSM_CACHE_PATH)

    if industrial_gdf.crs is None:
        industrial_gdf = industrial_gdf.set_crs("EPSG:4326")

    print(f"Loaded {len(industrial_gdf)} industrial features into memory")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "industrial_features_loaded": (
            len(industrial_gdf)
            if industrial_gdf is not None
            else 0
        )
    }


@app.get("/fires")
def get_fires(
    bbox: str = "76.5,27.5,78.0,29.0",
    days: int = 5
):
    """
    Fetch FIRMS hotspots for a bbox, run the full classification pipeline,
    and return classified & risk-scored clusters.
    """

    if not MAP_KEY:
        raise HTTPException(
            status_code=500,
            detail="FIRMS_MAP_KEY not configured on server"
        )

    try:
        raw = fetch_firms_data(MAP_KEY, bbox, days=days)
        cleaned = clean_firms_data(raw)

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"FIRMS fetch failed: {e}"
        )

    if cleaned.empty:
        return {
            "clusters": [],
            "message": "No hotspots found for this bbox/window"
        }

    results = run_pipeline(cleaned, industrial_gdf)

    # Convert timestamps to JSON-safe strings
    output = results.copy()

    for col in ["first_seen", "last_seen"]:
        if col in output.columns:
            output[col] = output[col].astype(str)

    return {
        "clusters": output.to_dict(orient="records")
    }


@app.get("/industrial")
def get_industrial():

    if industrial_gdf is None or industrial_gdf.empty:
        return {
            "type": "FeatureCollection",
            "features": []
        }

    gdf = industrial_gdf.to_crs("EPSG:4326")

    features = []

    for _, row in gdf.iterrows():

        geometry = row.geometry

        if geometry is None or geometry.is_empty:
            continue

        features.append({
            "type": "Feature",
            "geometry": mapping(geometry),
            "properties": {
                "id": row.get("id"),
                "name": row.get("name"),
                "landuse": row.get("landuse"),
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }
