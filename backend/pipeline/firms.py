from io import StringIO

import pandas as pd
import requests


# ============================================================
# FIRMS API
# ============================================================

def fetch_firms_data(
    map_key: str,
    bbox: str,
    days: int = 5,
    source: str = "VIIRS_SNPP_NRT",
) -> pd.DataFrame:
    """
    Fetch raw FIRMS active-fire data for a bounding box.
    """

    if not map_key:
        raise ValueError(
            "FIRMS MAP key is missing."
        )

    url = (
        "https://firms.modaps.eosdis.nasa.gov/"
        f"api/area/csv/"
        f"{map_key}/{source}/{bbox}/{days}"
    )

    response = requests.get(
        url,
        timeout=60,
    )

    response.raise_for_status()

    return pd.read_csv(
        StringIO(response.text)
    )


# ============================================================
# FIRMS cleaning
# ============================================================

def clean_firms_data(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize FIRMS fields and construct a UTC timestamp.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # --------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------

    required_columns = {
        "latitude",
        "longitude",
        "acq_date",
        "acq_time",
        "frp",
    }

    missing = required_columns - set(
        df.columns
    )

    if missing:
        raise ValueError(
            "FIRMS response is missing columns: "
            + ", ".join(sorted(missing))
        )

    # --------------------------------------------------------
    # Normalize acquisition date
    # --------------------------------------------------------

    df["acq_date"] = (
        df["acq_date"]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # Normalize acquisition time
    #
    # FIRMS commonly returns:
    #   2044
    #   0210
    #   930
    #
    # We normalize everything to HHMM.
    # --------------------------------------------------------

    df["acq_time"] = (
        pd.to_numeric(
            df["acq_time"],
            errors="coerce",
        )
        .astype("Int64")
        .astype(str)
        .str.replace(
            "<NA>",
            "",
            regex=False,
        )
        .str.zfill(4)
    )

    # --------------------------------------------------------
    # Construct timestamp safely
    # --------------------------------------------------------

    timestamp_text = (
        df["acq_date"]
        + " "
        + df["acq_time"].str[:2]
        + ":"
        + df["acq_time"].str[2:4]
    )

    df["acquired_at"] = pd.to_datetime(
        timestamp_text,
        errors="coerce",
        utc=True,
    )

    # --------------------------------------------------------
    # Numeric fields
    # --------------------------------------------------------

    for column in [
        "latitude",
        "longitude",
        "frp",
        "bright_ti4",
    ]:

        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if "confidence" in df.columns:

        confidence_map = {
            "l": "low",
            "n": "nominal",
            "h": "high",
        }

        df["confidence_label"] = (
            df["confidence"]
            .astype(str)
            .str.lower()
            .map(confidence_map)
            .fillna(
                df["confidence"]
                .astype(str)
            )
        )

    else:

        df["confidence_label"] = (
            "unknown"
        )

    # --------------------------------------------------------
    # Required output columns
    # --------------------------------------------------------

    keep_columns = [
        "latitude",
        "longitude",
        "acquired_at",
        "frp",
        "bright_ti4",
        "confidence_label",
        "satellite",
        "daynight",
    ]

    available_columns = [
        column
        for column in keep_columns
        if column in df.columns
    ]

    df = df[
        available_columns
    ].copy()

    # --------------------------------------------------------
    # Remove invalid rows
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
            "acquired_at",
            "frp",
        ]
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    return (
        df
        .sort_values(
            "acquired_at"
        )
        .reset_index(
            drop=True
        )
    )
