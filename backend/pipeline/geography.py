import json

from shapely.geometry import Point
import geopandas as gpd

from config import STATE_BOXES_PATH


# ============================================================
# State bounding boxes
# ============================================================

def load_state_boxes() -> dict[str, list[float]]:
    """Load state monitoring bounding boxes from JSON."""

    if not STATE_BOXES_PATH.exists():
        raise FileNotFoundError(
            f"State boxes file not found: {STATE_BOXES_PATH}"
        )

    with open(
        STATE_BOXES_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        boxes = json.load(file)

    if not isinstance(boxes, dict):
        raise ValueError(
            "state_boxes.json must contain a JSON object."
        )

    return boxes


STATE_BBOXES = load_state_boxes()


# ============================================================
# State validation
# ============================================================

def validate_state(state: str) -> str:
    """Validate a configured state name."""

    if not state:
        raise ValueError("State must be provided.")

    state = state.strip()

    if state not in STATE_BBOXES:
        raise ValueError(
            f"Unknown state '{state}'. "
            f"Available states: "
            f"{', '.join(sorted(STATE_BBOXES.keys()))}"
        )

    return state


# ============================================================
# State bbox
# ============================================================

def get_state_bbox(
    state: str,
) -> tuple[float, float, float, float]:
    """
    Return:
        west, south, east, north
    """

    state = validate_state(state)

    west, south, east, north = STATE_BBOXES[state]

    return (
        float(west),
        float(south),
        float(east),
        float(north),
    )


def get_state_bbox_string(
    state: str,
) -> str:
    """Return bbox in FIRMS API format."""

    west, south, east, north = get_state_bbox(
        state
    )

    return (
        f"{west},{south},{east},{north}"
    )


# ============================================================
# FIRMS -> GeoDataFrame
# ============================================================

def to_geodataframe(
    df,
) -> gpd.GeoDataFrame:
    """Convert FIRMS lat/lon columns into WGS84 points."""

    geometry = [
        Point(lon, lat)
        for lon, lat in zip(
            df["longitude"],
            df["latitude"],
        )
    ]

    return gpd.GeoDataFrame(
        df.copy(),
        geometry=geometry,
        crs="EPSG:4326",
    )
