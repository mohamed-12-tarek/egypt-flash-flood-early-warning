"""
ingestion/producer_live.py
Owner: Mohamed Tarek

Runs every hour (scheduled by Airflow). Fetches the latest weather
reading for every at-risk area from Open-Meteo's Forecast API, and
publishes each reading as a Kafka message matching the exact schema
in docs/data_contract.md (section 2).

This script does NOT write to the database directly — it only
publishes to Kafka. kafka_to_bronze_consumer.py is what writes the
messages into bronze.live_weather.

Run with:  uv run python ingestion/producer_live.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import json
import requests
from datetime import datetime, timezone
from kafka import KafkaProducer
from config import (
    AT_RISK_LOCATIONS,
    OPEN_METEO_FORECAST_URL,
    HOURLY_VARIABLES,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
)
from logger import get_logger


logger = get_logger("producer_live")


def fetch_latest_reading(city: str, lat: float, lon: float) -> dict:
    """Fetch the forecast API and return just the current hour's reading."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARIABLES),
        "forecast_days": 1,
    }
    response = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=30)
    response.raise_for_status()
    hourly = response.json()["hourly"]

    
    now_hour_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    if now_hour_str in hourly["time"]:
        idx = hourly["time"].index(now_hour_str)
    else:
        idx = 0 

    message = {"city": city, "time": hourly["time"][idx]}
    for var in HOURLY_VARIABLES:
        message[var] = hourly[var][idx]

    message["ingested_at"] = datetime.now(timezone.utc).isoformat()
    message["source"] = "live"
    return message


def main():
    logger.info("producer_live.py started")
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    sent_count = 0
    failed_cities = []

    for city, (lat, lon) in AT_RISK_LOCATIONS.items():
        try:
            message = fetch_latest_reading(city, lat, lon)
            producer.send(KAFKA_TOPIC, message).get(timeout=30)  
            sent_count += 1
            logger.info(f"Sent reading for {city}: {message}")
        except Exception:
            logger.error(f"Failed to fetch/send reading for {city}", exc_info=True)
            failed_cities.append(city)

    producer.flush()
    producer.close()

    if failed_cities:
        logger.warning(f"Finished with errors. Failed cities: {failed_cities}")
        sys.exit(1)  
    logger.info(f"producer_live.py finished. {sent_count} readings published.")

if __name__ == "__main__":
    main()
