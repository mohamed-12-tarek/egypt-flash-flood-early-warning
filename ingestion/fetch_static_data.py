"""
ingestion/fetch_static_data.py
Owner: Mohamed Tarek

ONE-TIME script — run once at the start of the project.

Fetches elevation for every at-risk area from Open-Elevation (one batch
request), estimates terrain slope using a nearby second point, and writes
the result into gold.dim_location — a table Khairy & Menna already created.

Run with:  uv run python ingestion/fetch_static_data.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import time
import requests
import pandas as pd
from sqlalchemy import text
from config import AT_RISK_LOCATIONS, OPEN_ELEVATION_URL, SLOPE_SAMPLE_OFFSET_DEG, KM_PER_DEGREE_LAT
from warehouse.db_connection import get_engine
from logger import get_logger

logger = get_logger("fetch_static_data")


def get_with_retry(url, params, retries=6, timeout=60):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException:
            logger.warning(f"Attempt {attempt}/{retries} failed", exc_info=True)
            if attempt == retries:
                raise
            time.sleep(5 * attempt)  # 5s, 10s, 15s...


def fetch_elevations(points: list) -> list:
    """One request for all points (list of (lat, lon))."""
    coords_str = "|".join(f"{lat},{lon}" for lat, lon in points)
    response = get_with_retry(OPEN_ELEVATION_URL, {"locations": coords_str})
    return [r["elevation"] for r in response.json()["results"]]


def build_dim_location_table() -> pd.DataFrame:
    cities = list(AT_RISK_LOCATIONS.keys())
    base_points = [AT_RISK_LOCATIONS[c] for c in cities]
    neighbor_points = [(lat + SLOPE_SAMPLE_OFFSET_DEG, lon) for lat, lon in base_points]

    logger.info(f"Fetching elevation for {len(cities)} locations + neighbors (1 request)...")
    elevations = fetch_elevations(base_points + neighbor_points)
    base_elev = elevations[:len(cities)]
    neighbor_elev = elevations[len(cities):]

    distance_km = SLOPE_SAMPLE_OFFSET_DEG * KM_PER_DEGREE_LAT
    rows = []
    for city, (lat, lon), e0, e1 in zip(cities, base_points, base_elev, neighbor_elev):
        slope = round(abs(e0 - e1) / distance_km, 2)
        rows.append({"city": city, "latitude": lat, "longitude": lon,
                     "elevation": e0, "slope_degree": slope})
        logger.info(f"{city}: elevation={e0}m, slope={slope}")
    return pd.DataFrame(rows)


if __name__ == "__main__":
    logger.info("=== fetch_static_data.py started ===")
    try:
        dim_location_df = build_dim_location_table()

        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM gold.dim_location"))
            dim_location_df.to_sql(
                "dim_location",
                con=conn,
                schema="gold",
                if_exists="append",
                index=False,
            )
        logger.info(f"Wrote {len(dim_location_df)} rows to gold.dim_location")
        logger.info("fetch_static_data.py finished successfully")
    except Exception:
        logger.error("fetch_static_data.py failed", exc_info=True)
        raise