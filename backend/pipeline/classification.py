import pandas as pd
import geopandas as gpd


# ============================================================
# Industrial Context
# ============================================================

def join_industrial_distance(
    hotspots_m: gpd.GeoDataFrame,
    industrial_m: gpd.GeoDataFrame,
    cluster_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find the nearest OSM industrial/context feature for each
    FIRMS detection and propagate the nearest context to the
    cluster level.
    """

    if industrial_m is None or len(industrial_m) == 0:
        result = cluster_features.copy()

        result["min_distance_to_industrial_m"] = float("inf")
        result["nearest_industry_category"] = "none"
        result["nearest_industry_name"] = None
        result["nearest_industry_state"] = None

        return result

    nearest = gpd.sjoin_nearest(
        hotspots_m,
        industrial_m,
        how="left",
        distance_col="distance_to_industrial_m",
    )

    nearest = nearest.sort_values(
        [
            "cluster_id",
            "distance_to_industrial_m",
        ]
    )

    nearest_cluster = (
        nearest
        .groupby(
            "cluster_id",
            as_index=False,
        )
        .first()
    )

    if "industry_category" in nearest_cluster.columns:
        category = (
            nearest_cluster["industry_category"]
            .fillna("unknown")
            .astype(str)
        )
    else:
        category = pd.Series(
            "unknown",
            index=nearest_cluster.index,
        )

    if "name" in nearest_cluster.columns:
        names = nearest_cluster["name"].where(
            nearest_cluster["name"].notna(),
            None,
        )
    else:
        names = pd.Series(
            None,
            index=nearest_cluster.index,
        )

    if "source_state" in nearest_cluster.columns:
        source_states = nearest_cluster[
            "source_state"
        ].where(
            nearest_cluster["source_state"].notna(),
            None,
        )
    else:
        source_states = pd.Series(
            None,
            index=nearest_cluster.index,
        )

    context = pd.DataFrame({
        "cluster_id":
            nearest_cluster["cluster_id"],

        "min_distance_to_industrial_m":
            nearest_cluster[
                "distance_to_industrial_m"
            ],

        "nearest_industry_category":
            category,

        "nearest_industry_name":
            names,

        "nearest_industry_state":
            source_states,
    })

    return cluster_features.merge(
        context,
        on="cluster_id",
        how="left",
    )


# ============================================================
# Classification
# ============================================================

def classify_cluster(
    row: pd.Series,
) -> dict:
    """
    Explainable rule-based classifier.

    Mining/quarry locations are explicitly separated from
    conventional industrial-fire contexts.
    """

    distance_m = row.get(
        "min_distance_to_industrial_m",
        float("inf"),
    )

    if pd.isna(distance_m):
        distance_m = float("inf")

    distance_km = distance_m / 1000.0

    category = str(
        row.get(
            "nearest_industry_category",
            "none",
        )
    ).lower()

    max_frp = float(
        row.get(
            "max_frp",
            0,
        )
    )

    is_persistent = bool(
        row.get(
            "is_persistent",
            False,
        )
    )

    distinct_days = int(
        row.get(
            "distinct_days",
            1,
        )
    )

    # --------------------------------------------------------
    # Mining
    # --------------------------------------------------------

    if category == "mining":
        return {
            "label":
                "mining_thermal_anomaly",

            "confidence":
                (
                    "medium"
                    if (
                        is_persistent
                        or max_frp >= 5
                    )
                    else "low"
                ),

            "reason":
                (
                    f"Thermal anomaly is "
                    f"{distance_km:.2f}km from a "
                    f"mapped mining area. "
                    f"Mining proximity alone is "
                    f"insufficient to classify it "
                    f"as an industrial fire."
                ),
        }

    # --------------------------------------------------------
    # Strong industrial contexts
    # --------------------------------------------------------

    strong_industrial = {
        "power_plant",
        "oil_petroleum",
        "gas_lng",
        "chemical_petrochemical",
        "steel_metal",
    }

    if (
        category in strong_industrial
        and distance_km <= 1.0
    ):
        return {
            "label":
                "likely_industrial_fire",

            "confidence":
                (
                    "high"
                    if is_persistent
                    else "medium"
                ),

            "reason":
                (
                    f"Thermal anomaly within "
                    f"{distance_km:.2f}km of "
                    f"{format_category(category)}"
                ),
        }

    # --------------------------------------------------------
    # General industrial area
    # --------------------------------------------------------

    if (
        category == "industrial_general"
        and distance_km <= 1.0
    ):
        return {
            "label":
                "likely_industrial_fire",

            "confidence":
                (
                    "high"
                    if is_persistent
                    else "medium"
                ),

            "reason":
                (
                    f"Thermal anomaly within "
                    f"{distance_km:.2f}km of a "
                    f"mapped industrial area"
                ),
        }

    # --------------------------------------------------------
    # Possible industrial
    # --------------------------------------------------------

    if (
        distance_km <= 10.0
        and category not in {
            "mining",
            "none",
        }
    ):
        return {
            "label":
                "possible_industrial_fire",

            "confidence":
                (
                    "medium"
                    if (
                        is_persistent
                        or max_frp >= 3.0
                    )
                    else "low"
                ),

            "reason":
                (
                    f"{distance_km:.1f}km from "
                    f"{format_category(category)}, "
                    f"{'persistent' if is_persistent else 'single detection'}, "
                    f"FRP={max_frp:.2f}"
                ),
        }

    # --------------------------------------------------------
    # Persistent high-FRP, far from industry
    # --------------------------------------------------------

    if (
        is_persistent
        and max_frp >= 5.0
        and distance_km > 10.0
    ):
        return {
            "label":
                "likely_agricultural_or_wildfire",

            "confidence":
                "high",

            "reason":
                (
                    f"Persistent ({distinct_days} days) "
                    f"and high FRP but "
                    f"{distance_km:.1f}km from "
                    f"industrial infrastructure"
                ),
        }

    # --------------------------------------------------------
    # Isolated low-FRP detection
    # --------------------------------------------------------

    if (
        distance_km > 10.0
        and not is_persistent
        and max_frp < 5.0
    ):
        return {
            "label":
                "low_priority_false_positive",

            "confidence":
                "medium",

            "reason":
                (
                    f"Isolated single-day detection, "
                    f"{distance_km:.1f}km from "
                    f"industrial infrastructure"
                ),
        }

    # --------------------------------------------------------
    # Uncertain
    # --------------------------------------------------------

    return {
        "label":
            "uncertain",

        "confidence":
            "low",

        "reason":
            (
                "Does not match a clear rule "
                "pattern and requires manual review."
            ),
    }


# ============================================================
# Risk Score
# ============================================================

def compute_risk_score(
    row: pd.Series,
) -> float:

    label_base = {
        "likely_industrial_fire": 70,
        "possible_industrial_fire": 45,
        "mining_thermal_anomaly": 15,
        "likely_agricultural_or_wildfire": 20,
        "low_priority_false_positive": 5,
        "uncertain": 15,
    }

    confidence_multiplier = {
        "high": 1.0,
        "medium": 0.8,
        "low": 0.6,
    }

    base = label_base.get(
        row["label"],
        15,
    )

    confidence = confidence_multiplier.get(
        row["confidence"],
        0.6,
    )

    frp_bonus = min(
        float(row["max_frp"]),
        20,
    )

    persistence_bonus = min(
        int(row["distinct_days"]) * 3,
        10,
    )

    return round(
        min(
            (
                base * confidence
                + frp_bonus
                + persistence_bonus
            ),
            100,
        ),
        1,
    )


# ============================================================
# Formatting
# ============================================================

def format_category(
    category: str,
) -> str:

    categories = {
        "power_plant":
            "power plant",

        "oil_petroleum":
            "oil/petroleum facility",

        "gas_lng":
            "gas/LNG facility",

        "chemical_petrochemical":
            "chemical/petrochemical facility",

        "steel_metal":
            "steel/metal facility",

        "industrial_general":
            "industrial facility",

        "mining":
            "mining area",

        "other_industrial":
            "industrial site",

        "unknown":
            "mapped industrial site",

        "none":
            "no mapped industrial site",
    }

    return categories.get(
        category,
        category.replace(
            "_",
            " ",
        ),
    )
