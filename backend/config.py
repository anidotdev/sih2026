from pathlib import Path


# ============================================================
# Project paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

CONFIG_DIR = BASE_DIR / "config"

STATE_BOXES_PATH = (
    CONFIG_DIR / "state_boxes.json"
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Geospatial configuration
# ============================================================

# Current prototype is focused on North India.
METRIC_CRS = "EPSG:32643"


# ============================================================
# Clustering configuration
# ============================================================

CLUSTER_EPS_METERS = 2000

CLUSTER_MIN_SAMPLES = 1
