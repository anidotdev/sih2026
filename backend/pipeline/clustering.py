import numpy as np
import pandas as pd
import geopandas as gpd

from sklearn.cluster import DBSCAN

from config import (
    CLUSTER_EPS_METERS,
    CLUSTER_MIN_SAMPLES,
)


# ============================================================
# Spatial clustering
# ============================================================

def cluster_hotspots(
    hotspots_m: gpd.GeoDataFrame,
    eps: float = CLUSTER_EPS_METERS,
    min_samples: int = CLUSTER_MIN_SAMPLES,
) -> gpd.GeoDataFrame:
    """
    Run DBSCAN over projected metric coordinates.

    hotspots_m must use a metric CRS.
    """

    if hotspots_m.empty:
        result = hotspots_m.copy()
        result["cluster_id"] = pd.Series(
            dtype=int
        )
        return result

    coords = [
        (
            geometry.x,
            geometry.y,
        )
        for geometry in hotspots_m.geometry
    ]

    coords_df = pd.DataFrame(
        coords,
        columns=[
            "x",
            "y",
        ],
    )

    db = DBSCAN(
        eps=eps,
        min_samples=min_samples,
    )

    labels = db.fit_predict(
        coords_df[
            [
                "x",
                "y",
            ]
        ]
    )

    result = hotspots_m.copy()

    result[
        "cluster_id"
    ] = labels

    return result


# ============================================================
# Cluster-level feature engineering
# ============================================================

def compute_cluster_features(
    gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Reduce FIRMS detections into one feature row per cluster.

    The output intentionally matches the feature schema used
    by the trained Random Forest:

        detection_count
        distinct_days
        mean_frp
        max_frp
        frp_std
        mean_bright_ti4
        max_bright_ti4
        persistence_days
        min_distance_to_industrial_m
        day_ratio

    `min_distance_to_industrial_m` is added later by
    join_industrial_distance().
    """

    if gdf.empty:
        return pd.DataFrame(
            columns=[
                "cluster_id",
                "detection_count",
                "distinct_days",
                "first_seen",
                "last_seen",
                "mean_frp",
                "max_frp",
                "frp_std",
                "mean_bright_ti4",
                "max_bright_ti4",
                "centroid_lat",
                "centroid_lon",
                "persistence_days",
                "is_persistent",
                "day_ratio",
            ]
        )

    gdf = gdf.copy()


    # --------------------------------------------------------
    # Acquisition date
    # --------------------------------------------------------

    gdf[
        "acq_date_only"
    ] = (
        pd.to_datetime(
            gdf[
                "acquired_at"
            ],
            errors="coerce",
            utc=True,
        )
        .dt.date
    )


    # --------------------------------------------------------
    # Normalize numeric thermal fields
    # --------------------------------------------------------

    if "frp" in gdf.columns:

        gdf[
            "frp"
        ] = pd.to_numeric(
            gdf[
                "frp"
            ],
            errors="coerce",
        )


    if "bright_ti4" in gdf.columns:

        gdf[
            "bright_ti4"
        ] = pd.to_numeric(
            gdf[
                "bright_ti4"
            ],
            errors="coerce",
        )


    # --------------------------------------------------------
    # Safe standard deviation
    # --------------------------------------------------------

    def safe_std(
        series: pd.Series,
    ) -> float:

        series = pd.to_numeric(
            series,
            errors="coerce",
        ).dropna()

        if len(series) <= 1:
            return 0.0

        value = series.std()

        if pd.isna(value):
            return 0.0

        return float(value)


    # --------------------------------------------------------
    # Base aggregations
    # --------------------------------------------------------

    aggregations = {

        "detection_count": (
            "cluster_id",
            "size",
        ),

        "distinct_days": (
            "acq_date_only",
            "nunique",
        ),

        "first_seen": (
            "acquired_at",
            "min",
        ),

        "last_seen": (
            "acquired_at",
            "max",
        ),

        "mean_frp": (
            "frp",
            "mean",
        ),

        "max_frp": (
            "frp",
            "max",
        ),

        "frp_std": (
            "frp",
            safe_std,
        ),

        "centroid_lat": (
            "latitude",
            "mean",
        ),

        "centroid_lon": (
            "longitude",
            "mean",
        ),
    }


    # --------------------------------------------------------
    # Brightness features
    # --------------------------------------------------------
    #
    # Some historical FIRMS files don't provide bright_ti4.
    # Keep the production schema consistent by creating
    # NaN columns when the field is unavailable.
    # --------------------------------------------------------

    if "bright_ti4" in gdf.columns:

        aggregations[
            "mean_bright_ti4"
        ] = (
            "bright_ti4",
            "mean",
        )

        aggregations[
            "max_bright_ti4"
        ] = (
            "bright_ti4",
            "max",
        )


    # --------------------------------------------------------
    # Aggregate
    # --------------------------------------------------------

    features = (
        gdf
        .groupby(
            "cluster_id"
        )
        .agg(
            **aggregations
        )
        .reset_index()
    )


    # --------------------------------------------------------
    # Ensure brightness schema exists
    # --------------------------------------------------------

    if (
        "mean_bright_ti4"
        not in features.columns
    ):

        features[
            "mean_bright_ti4"
        ] = np.nan


    if (
        "max_bright_ti4"
        not in features.columns
    ):

        features[
            "max_bright_ti4"
        ] = np.nan


    # --------------------------------------------------------
    # Day/night feature
    # --------------------------------------------------------
    #
    # Live FIRMS may have daynight.
    # Some historical files don't.
    # --------------------------------------------------------

    if "daynight" in gdf.columns:

        day_ratio = (
            gdf
            .groupby(
                "cluster_id"
            )[
                "daynight"
            ]
            .apply(
                lambda series:
                    float(
                        (
                            series
                            .astype(str)
                            .str
                            .upper()
                            == "D"
                        ).mean()
                    )
            )
            .rename(
                "day_ratio"
            )
            .reset_index()
        )

        features = features.merge(
            day_ratio,
            on="cluster_id",
            how="left",
        )

    else:

        features[
            "day_ratio"
        ] = np.nan


    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    features[
        "persistence_days"
    ] = (
        (
            features[
                "last_seen"
            ]
            -
            features[
                "first_seen"
            ]
        )
        .dt.total_seconds()
        / 86400.0
    )


    # --------------------------------------------------------
    # Binary persistence indicator
    #
    # Not used directly by the ML model, but useful elsewhere
    # in the API/dashboard.
    # --------------------------------------------------------

    features[
        "is_persistent"
    ] = (
        features[
            "distinct_days"
        ]
        >= 2
    )


    # --------------------------------------------------------
    # Clean numeric outputs
    # --------------------------------------------------------

    numeric_columns = [
        "detection_count",
        "distinct_days",
        "mean_frp",
        "max_frp",
        "frp_std",
        "mean_bright_ti4",
        "max_bright_ti4",
        "persistence_days",
        "day_ratio",
        "centroid_lat",
        "centroid_lon",
    ]

    for column in numeric_columns:

        if column in features.columns:

            features[
                column
            ] = pd.to_numeric(
                features[
                    column
                ],
                errors="coerce",
            )


    # --------------------------------------------------------
    # Final ordering
    # --------------------------------------------------------

    preferred_columns = [
        "cluster_id",
        "detection_count",
        "distinct_days",
        "first_seen",
        "last_seen",
        "mean_frp",
        "max_frp",
        "frp_std",
        "mean_bright_ti4",
        "max_bright_ti4",
        "centroid_lat",
        "centroid_lon",
        "persistence_days",
        "is_persistent",
        "day_ratio",
    ]

    available_columns = [
        column
        for column in preferred_columns
        if column in features.columns
    ]

    features = features[
        available_columns
    ]


    return (
        features
        .sort_values(
            "cluster_id"
        )
        .reset_index(
            drop=True
        )
    )
