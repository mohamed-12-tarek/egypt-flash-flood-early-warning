"""
ingestion/kafka_to_bronze_consumer.py
Owner: Mohamed Tarek

A simple Kafka consumer. Runs continuously (or triggered hourly right
after producer_live.py by Airflow — see orchestration/dags). Reads
every new message from the flood-risk-raw topic and inserts it as-is
(no cleaning) into bronze.live_weather, a table Khairy & Menna already created.

Run with:  uv run python ingestion/kafka_to_bronze_consumer.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import json
import pandas as pd
from kafka import KafkaConsumer
from config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, HOURLY_VARIABLES
from warehouse.db_connection import get_engine
from logger import get_logger


logger = get_logger("kafka_to_bronze_consumer")


def main():
    logger.info("kafka_to_bronze_consumer.py started")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="bronze-writer",
        consumer_timeout_ms=30000
    )

    engine = get_engine()
    columns = ["city", "event_time"] + HOURLY_VARIABLES + ["source"]

    rows_written = 0
    rows_failed = 0

    for message in consumer:
        data = message.value
        try:
            row = {
                "city": data["city"],
                "event_time": data["time"],
                "source": data.get("source", "live"),
            }
            for var in HOURLY_VARIABLES:
                row[var] = data.get(var)

            df = pd.DataFrame([row])[columns]
            df.to_sql("live_weather", con=engine, schema="bronze", if_exists="append", index=False)
            rows_written += 1
            logger.info(f"Wrote reading for {row['city']} at {row['event_time']}")
        except Exception:
            rows_failed += 1
            logger.error(f"Failed to write message to bronze.live_weather: {data}", exc_info=True)

    consumer.close()
    if rows_failed:
        logger.warning(f"{rows_failed} messages failed to write this run.")
    logger.info(f"kafka_to_bronze_consumer.py finished. {rows_written} rows written.")


if __name__ == "__main__":
    main()