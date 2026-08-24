import os
import geopandas as gpd

from dotenv import load_dotenv

from pipeline import (
    fetch_firms_data,
    clean_firms_data,
    run_pipeline,
)


# ============================================================
# Configuration
# ============================================================

# Load variables from .env
load_dotenv()

MAP_KEY = os.getenv("FIRMS_MAP_KEY")

if not MAP_KEY:
    raise ValueError(
        "FIRMS_MAP_KEY is not set. "
        "Add it to your .env file."
    )

BBOX = "76.5,27.5,78.0,29.0"

OSM_CACHE_PATH = "data/osm_industrial_ncr_haryana.parquet"


# ============================================================
# 1. Fetch FIRMS
# ============================================================

print("\n=== FIRMS ===")

raw = fetch_firms_data(
    MAP_KEY,
    BBOX,
    days=5,
)

cleaned = clean_firms_data(raw)

print("FIRMS rows:", cleaned.shape)

if cleaned.empty:
    raise RuntimeError(
        "No FIRMS hotspots were returned."
    )


# ============================================================
# 2. Load OSM cache
# ============================================================

print("\n=== OSM INDUSTRIAL DATA ===")

if not os.path.exists(OSM_CACHE_PATH):
    raise FileNotFoundError(
        f"\nOSM cache not found:\n{OSM_CACHE_PATH}\n\n"
        "Create this regional parquet first. "
        "The pipeline will not query Overpass automatically."
    )

industrial = gpd.read_parquet(OSM_CACHE_PATH)

print("Loaded:", OSM_CACHE_PATH)
print("Industrial features:", industrial.shape)


# ============================================================
# 3. Validate geometry
# ============================================================

if industrial.crs is None:
    industrial = industrial.set_crs("EPSG:4326")

elif industrial.crs.to_epsg() != 4326:
    industrial = industrial.to_crs("EPSG:4326")


industrial = industrial[
    industrial.geometry.notna()
].copy()

industrial = industrial[
    ~industrial.geometry.is_empty
].copy()


# ============================================================
# 4. Run pipeline
# ============================================================

print("\n=== RUNNING PIPELINE ===")

results = run_pipeline(
    cleaned,
    industrial,
)


# ============================================================
# 5. Display results
# ============================================================

print("\n=== RESULTS ===")

columns = [
    "cluster_id",
    "detection_count",
    "is_persistent",
    "max_frp",
    "label",
    "confidence",
    "risk_score",
]

columns = [
    column
    for column in columns
    if column in results.columns
]

print(results[columns].to_string(index=False))
