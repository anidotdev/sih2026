import os
import re
import threading

import geopandas as gpd

from config import DATA_DIR
from .geography import validate_state


# ============================================================
# In-memory state cache
# ============================================================

_STATE_CACHE: dict[str, gpd.GeoDataFrame] = {}

_CACHE_LOCK = threading.Lock()

def get_loaded_states() -> list[str]:
    """
    Return the states currently loaded in the
    in-memory industrial cache.
    """
    return sorted(_STATE_CACHE.keys())


# ============================================================
# File path
# ============================================================

def get_state_parquet_path(
    state: str,
) -> str:
    """Return the Parquet path for a state."""

    state = validate_state(state)

    safe_state_name = re.sub(
        r"[^a-z0-9]+",
        "_",
        state.lower(),
    ).strip("_")

    return os.path.join(
        str(DATA_DIR),
        f"osm_industrial_{safe_state_name}.parquet",
    )


# ============================================================
# Load one state
# ============================================================

def load_industrial_for_state(
    state: str,
) -> gpd.GeoDataFrame:
    """
    Load one state's industrial reference layer.

    The first request reads the Parquet from disk.
    Later requests reuse the in-memory GeoDataFrame.
    """

    state = validate_state(state)

    # --------------------------------------------------------
    # Fast path
    # --------------------------------------------------------

    if state in _STATE_CACHE:
        return _STATE_CACHE[state]


    # --------------------------------------------------------
    # Thread-safe loading
    # --------------------------------------------------------

    with _CACHE_LOCK:

        if state in _STATE_CACHE:
            return _STATE_CACHE[state]

        path = get_state_parquet_path(
            state
        )

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Industrial dataset not found "
                f"for {state}: {path}"
            )

        print(
            f"[industrial] loading "
            f"{state} from {path}"
        )

        gdf = gpd.read_parquet(
            path
        )

        if gdf.empty:
            raise ValueError(
                f"Industrial dataset for "
                f"{state} is empty."
            )

        if gdf.crs is None:
            gdf = gdf.set_crs(
                "EPSG:4326"
            )
        else:
            gdf = gdf.to_crs(
                "EPSG:4326"
            )

        # Remove invalid geometries.
        gdf = gdf[
            gdf.geometry.notna()
        ].copy()

        gdf = gdf[
            ~gdf.geometry.is_empty
        ].copy()

        # Create spatial index once.
        # Accessing sindex forces GeoPandas to build it.
        _ = gdf.sindex

        _STATE_CACHE[state] = gdf

        print(
            f"[industrial] cached "
            f"{state}: {len(gdf)} features"
        )

        return gdf


# ============================================================
# Cache management
# ============================================================

def get_loaded_states() -> list[str]:
    """Return states currently cached in memory."""

    return sorted(
        _STATE_CACHE.keys()
    )


def clear_state_cache() -> None:
    """Clear the in-memory industrial cache."""

    _STATE_CACHE.clear()

    print(
        "[industrial] state cache cleared"
    )
