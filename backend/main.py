# ============================================================
# Industrial Fire Detection API
# ============================================================

import os

import pandas as pd

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.middleware.cors import CORSMiddleware

from shapely.geometry import mapping

from pipeline import (
    fetch_firms_data,
    clean_firms_data,
    run_pipeline,
    load_industrial_for_state,
    get_state_bbox_string,
    validate_state,
)


# ============================================================
# Environment
# ============================================================

load_dotenv()

MAP_KEY = os.getenv(
    "FIRMS_MAP_KEY"
)


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="Industrial Fire Detection API",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:4321",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Startup
# ============================================================

@app.on_event("startup")
def startup():

    if not MAP_KEY:
        raise RuntimeError(
            "FIRMS_MAP_KEY is not configured"
        )

    print(
        "Industrial Fire Detection API started."
    )

    print(
        "Industrial state datasets "
        "will be loaded on demand."
    )


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "firms_configured": bool(MAP_KEY),
    }


# ============================================================
# Available States
# ============================================================

@app.get("/states")
def get_states():
    """
    Return all states configured in
    state_boxes.json.
    """

    from pipeline.geography import (
        STATE_BBOXES,
    )

    states = []

    for state in sorted(
        STATE_BBOXES.keys()
    ):

        try:

            bbox = (
                get_state_bbox_string(
                    state
                )
            )

            states.append({
                "name": state,
                "bbox": bbox,
            })

        except Exception:
            continue

    return {
        "states": states
    }


# ============================================================
# Fires
# ============================================================

@app.get("/fires")
def get_fires(
    state: str = "Haryana",
    days: int = 5,
):
    """
    Fetch FIRMS hotspots for a selected state,
    run clustering/classification, and return
    risk-ranked clusters.
    """

    if not MAP_KEY:

        raise HTTPException(
            status_code=500,
            detail=(
                "FIRMS_MAP_KEY "
                "not configured"
            ),
        )


    # --------------------------------------------------------
    # Validate days
    # --------------------------------------------------------

    if days < 1:

        raise HTTPException(
            status_code=400,
            detail="days must be >= 1",
        )


    if days > 5:

        raise HTTPException(
            status_code=400,
            detail=(
                "days must be <= 5 "
                "for this FIRMS request"
            ),
        )


    # --------------------------------------------------------
    # Validate state
    # --------------------------------------------------------

    try:

        state = validate_state(
            state
        )

        bbox = (
            get_state_bbox_string(
                state
            )
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


    # --------------------------------------------------------
    # Fetch FIRMS
    # --------------------------------------------------------

    try:

        raw = fetch_firms_data(
            map_key=MAP_KEY,
            bbox=bbox,
            days=days,
            source="VIIRS_SNPP_NRT",
        )

        cleaned = clean_firms_data(
            raw
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"FIRMS fetch failed: "
                f"{exc}"
            ),
        )


    # --------------------------------------------------------
    # No detections
    # --------------------------------------------------------

    if cleaned.empty:

        return {
            "state": state,
            "bbox": bbox,
            "hotspot_count": 0,
            "clusters": [],
            "message": (
                "No hotspots found "
                "for this state/window"
            ),
        }


    # --------------------------------------------------------
    # Run pipeline
    # --------------------------------------------------------

    try:

        results = run_pipeline(
            hotspots_df=cleaned,
            state=state,
        )

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Pipeline processing failed: "
                f"{exc}"
            ),
        )


    # --------------------------------------------------------
    # JSON-safe output
    # --------------------------------------------------------

    output = results.copy()


    for column in [
        "first_seen",
        "last_seen",
    ]:

        if column in output.columns:

            output[column] = (
                output[column]
                .astype(str)
            )


    # Convert inf/-inf to None.
    output = output.replace(
        [
            float("inf"),
            float("-inf"),
        ],
        None,
    )


    # Convert NaN / NaT to None.
    output = (
        output
        .astype(object)
        .where(
            pd.notna(output),
            None,
        )
    )


    return {
        "state": state,
        "bbox": bbox,
        "hotspot_count": len(cleaned),
        "clusters": output.to_dict(
            orient="records"
        ),
    }


# ============================================================
# Industrial Layer
# ============================================================

@app.get("/industrial")
def get_industrial(
    state: str = "Haryana",
):
    """
    Return the industrial reference layer
    for one selected state.

    The state Parquet is loaded on demand
    by the industrial module.
    """

    # --------------------------------------------------------
    # Validate state
    # --------------------------------------------------------

    try:

        state = validate_state(
            state
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


    # --------------------------------------------------------
    # Load Parquet
    # --------------------------------------------------------

    try:

        gdf = (
            load_industrial_for_state(
                state
            )
        )

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to load industrial "
                f"data: {exc}"
            ),
        )


    # --------------------------------------------------------
    # Empty layer
    # --------------------------------------------------------

    if gdf.empty:

        return {
            "type":
                "FeatureCollection",

            "state":
                state,

            "feature_count":
                0,

            "features":
                [],
        }


    # --------------------------------------------------------
    # GeoJSON requires WGS84
    # --------------------------------------------------------

    gdf = gdf.to_crs(
        "EPSG:4326"
    )


    features = []


    # --------------------------------------------------------
    # GeoDataFrame -> GeoJSON
    # --------------------------------------------------------

    for _, row in gdf.iterrows():

        geometry = row.geometry


        if (
            geometry is None
            or geometry.is_empty
        ):
            continue


        properties = {
            "id":
                row.get("id"),

            "name":
                row.get("name"),

            "landuse":
                row.get("landuse"),

            "industrial":
                row.get("industrial"),

            "man_made":
                row.get("man_made"),

            "power":
                row.get("power"),

            "content":
                row.get("content"),

            "product":
                row.get("product"),

            "works":
                row.get("works"),

            "industry_category":
                row.get(
                    "industry_category"
                ),

            "source_state":
                row.get(
                    "source_state",
                    state,
                ),

            "geometry_type":
                row.get(
                    "geometry_type"
                ),
        }


        # ----------------------------------------------------
        # Convert NaN / NaT -> None
        # ----------------------------------------------------

        properties = {
            key: (
                None
                if pd.isna(value)
                else value
            )

            for key, value
            in properties.items()
        }


        features.append({
            "type":
                "Feature",

            "geometry":
                mapping(
                    geometry
                ),

            "properties":
                properties,
        })


    return {
        "type":
            "FeatureCollection",

        "state":
            state,

        "feature_count":
            len(features),

        "features":
            features,
    }
