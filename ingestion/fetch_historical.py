"""
ingestion/fetch_historical.py
Owner: Mohamed Tarek

ONE-TIME script. Fetches hourly historical weather for every at-risk area
from Open-Meteo and writes raw rows into bronze.historical_weather.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import time
import requests
import pandas as pd
from sqlalchemy import text
from config import AT_RISK_LOCATIONS, OPEN_METEO_HISTORICAL_URL, HOURLY_VARIABLES
from warehouse.db_connection import get_engine
from logger import get_logger

logger = get_logger("fetch_historical")

START_DATE = "2019-01-01"
END_DATE = "2024-12-31"


def fetch_historical_for_city(city: str, lat: float, lon: float) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": ",".join(HOURLY_VARIABLES),
    }
    for attempt in range(1, 6):
        try:
            response = requests.get(OPEN_METEO_HISTORICAL_URL, params=params, timeout=120)
            response.raise_for_status()
            break
        except requests.RequestException:
            logger.warning(f"{city}: attempt {attempt}/5 failed", exc_info=True)
            if attempt == 5:
                raise
            time.sleep(20 * attempt)

    city_df = pd.DataFrame(response.json()["hourly"]).rename(columns={"time": "event_time"})
    city_df["city"] = city
    city_df["source"] = "historical"
    return city_df


if __name__ == "__main__":
    logger.info("fetch_historical.py started")
    engine = get_engine()
    total_rows = 0
    failed_cities = []

    for city, (lat, lon) in AT_RISK_LOCATIONS.items():
        logger.info(f"Fetching historical data for {city} ({START_DATE} to {END_DATE})...")
        try:
            city_df = fetch_historical_for_city(city, lat, lon)
            columns = ["city", "event_time"] + HOURLY_VARIABLES + ["source"]
            city_df = city_df[columns]

            # Idempotent: delete this city's old rows first, so retries never duplicate
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM bronze.historical_weather WHERE city = :c"),
                    {"c": city},
                )

            city_df.to_sql(
                "historical_weather", con=engine, schema="bronze",
                if_exists="append", index=False, chunksize=1000,
            )
            total_rows += len(city_df)
            logger.info(f"{city}: wrote {len(city_df)} rows")
            time.sleep(5)
        except Exception:
            logger.error(f"Failed to fetch/write historical data for {city}", exc_info=True)
            failed_cities.append(city)

    if failed_cities:
        logger.warning(f"Finished with errors. Failed cities: {failed_cities}")
        sys.exit(1)  # make the Airflow task FAIL instead of showing green
    logger.info(f"fetch_historical.py finished. {total_rows} total rows written.")