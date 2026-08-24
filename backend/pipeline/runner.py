# pipeline/runner.py

import pandas as pd
import geopandas as gpd

from config import METRIC_CRS

from .firms import (
    fetch_firms_data,
    clean_firms_data,
)

from .geography import (
    to_geodataframe,
    validate_state,
    get_state_bbox_string,
)

from .industrial import (
    load_industrial_for_state,
)

from .clustering import (
    cluster_hotspots,
    compute_cluster_features,
)

from .classification import (
    join_industrial_distance,
)

from ml import (
    classify_clusters_ml,
)


# ============================================================
# JSON sanitization
# ============================================================

def sanitize_for_json(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    result = result.replace(
        [
            float("inf"),
            float("-inf"),
        ],
        None,
    )

    result = (
        result
        .astype(object)
        .where(
            pd.notna(result),
            None,
        )
    )

    return result


# ============================================================
# ML confidence -> human-readable confidence
# ============================================================

def confidence_label(
    value,
) -> str:

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return "low"

    if value >= 0.80:
        return "high"

    if value >= 0.60:
        return "medium"

    return "low"


# ============================================================
# ML assessment text
# ============================================================

def build_ml_reason(
    row: pd.Series,
) -> str:

    label = str(
        row.get(
            "label",
            "unknown",
        )
    )

    confidence = float(
        row.get(
            "model_confidence",
            0.0,
        )
    )

    persistence = int(
        row.get(
            "distinct_days",
            0,
        )
    )

    max_frp = float(
        row.get(
            "max_frp",
            0.0,
        )
    )

    distance = row.get(
        "min_distance_to_industrial_m"
    )

    if pd.isna(distance):
        distance_text = "unknown"
    else:
        distance_text = (
            f"{float(distance) / 1000:.2f} km"
        )

    if label == "static_thermal_source":
        return (
            f"ML classified this location as "
            f"a static thermal source with "
            f"{confidence:.1%} confidence. "
            f"Persistence: {persistence} days; "
            f"maximum FRP: {max_frp:.2f}; "
            f"nearest mapped industrial context: "
            f"{distance_text}. "
            f"This is not automatically treated "
            f"as an industrial fire."
        )

    if label == "vegetation_fire":
        return (
            f"ML classified this location as "
            f"a vegetation-fire pattern with "
            f"{confidence:.1%} confidence. "
            f"Persistence: {persistence} days; "
            f"maximum FRP: {max_frp:.2f}; "
            f"nearest mapped industrial context: "
            f"{distance_text}."
        )

    return (
        f"ML classified this location as "
        f"{label} with "
        f"{confidence:.1%} confidence."
    )


# ============================================================
# ML-based risk score
# ============================================================

def compute_ml_risk_score(
    row: pd.Series,
) -> float:
    """
    Risk is deliberately different from classification.

    static_thermal_source receives a low base score because
    persistent heat at mines/refineries/power facilities
    should not automatically become a fire alert.

    The model class is still preserved in `label`.
    """

    label = str(
        row.get(
            "label",
            "unknown",
        )
    )

    confidence = float(
        row.get(
            "model_confidence",
            0.0,
        )
    )

    max_frp = float(
        row.get(
            "max_frp",
            0.0,
        )
    )

    distinct_days = int(
        row.get(
            "distinct_days",
            0,
        )
    )


    base_scores = {
        "static_thermal_source": 15,
        "vegetation_fire": 20,

        # Future classes can be added here
        # without changing the pipeline.
        "industrial_fire": 80,
        "gas_flare": 30,
        "mining_activity": 20,
        "wildfire": 20,
        "agricultural_burning": 15,
        "other": 10,
    }


    base = base_scores.get(
        label,
        10,
    )


    confidence_component = (
        base * confidence
    )


    frp_component = min(
        max_frp,
        20,
    )


    persistence_component = min(
        distinct_days * 2,
        10,
    )


    return round(
        min(
            confidence_component
            + frp_component
            + persistence_component,
            100,
        ),
        1,
    )


# ============================================================
# Main pipeline
# ============================================================

def run_pipeline(
    hotspots_df: pd.DataFrame,
    state: str,
    industrial_gdf: gpd.GeoDataFrame | None = None,
) -> pd.DataFrame:

    state = validate_state(
        state
    )

    if hotspots_df.empty:
        return pd.DataFrame()


    # --------------------------------------------------------
    # FIRMS -> GeoDataFrame
    # --------------------------------------------------------

    hotspots = to_geodataframe(
        hotspots_df
    )

    if hotspots.empty:
        return pd.DataFrame()


    # --------------------------------------------------------
    # Metric projection
    # --------------------------------------------------------

    hotspots_m = hotspots.to_crs(
        METRIC_CRS
    )


    # --------------------------------------------------------
    # DBSCAN
    # --------------------------------------------------------

    hotspots_m = cluster_hotspots(
        hotspots_m
    )


    # --------------------------------------------------------
    # Cluster features
    # --------------------------------------------------------

    cluster_features = (
        compute_cluster_features(
            hotspots_m
        )
    )

    if cluster_features.empty:
        return pd.DataFrame()


    # --------------------------------------------------------
    # Industrial reference layer
    # --------------------------------------------------------

    if industrial_gdf is None:
        industrial_gdf = (
            load_industrial_for_state(
                state
            )
        )


    if (
        industrial_gdf is not None
        and not industrial_gdf.empty
    ):

        industrial_m = (
            industrial_gdf
            .to_crs(
                METRIC_CRS
            )
        )

    else:

        industrial_m = industrial_gdf


    # --------------------------------------------------------
    # OSM context
    #
    # IMPORTANT:
    # OSM is now contextual information.
    # It is NOT the classifier.
    # --------------------------------------------------------

    cluster_features = (
        join_industrial_distance(
            hotspots_m,
            industrial_m,
            cluster_features,
        )
    )


    # --------------------------------------------------------
    # ML CLASSIFIER
    # --------------------------------------------------------

    result = (
        classify_clusters_ml(
            cluster_features
        )
    )


    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    result[
        "confidence"
    ] = (
        result[
            "model_confidence"
        ]
        .apply(
            confidence_label
        )
    )


    # --------------------------------------------------------
    # Human-readable assessment
    # --------------------------------------------------------

    result[
        "reason"
    ] = result.apply(
        build_ml_reason,
        axis=1,
    )


    # --------------------------------------------------------
    # Risk score
    # --------------------------------------------------------

    result[
        "risk_score"
    ] = result.apply(
        compute_ml_risk_score,
        axis=1,
    )


    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    result[
        "state"
    ] = state


    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    result = (
        result
        .sort_values(
            "risk_score",
            ascending=False,
        )
        .reset_index(
            drop=True,
        )
    )


    return sanitize_for_json(
        result
    )


# ============================================================
# End-to-end pipeline
# ============================================================

def run_full_pipeline(
    map_key: str,
    state: str,
    days: int = 5,
    source: str = "VIIRS_SNPP_NRT",
) -> pd.DataFrame:

    state = validate_state(
        state
    )

    bbox = get_state_bbox_string(
        state
    )


    raw = fetch_firms_data(
        map_key=map_key,
        bbox=bbox,
        days=days,
        source=source,
    )


    cleaned = clean_firms_data(
        raw
    )


    if cleaned.empty:
        return pd.DataFrame()


    return run_pipeline(
        hotspots_df=cleaned,
        state=state,
    )
