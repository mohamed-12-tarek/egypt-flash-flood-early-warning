"""
dag_hourly_ingestion.py
Owner: Mohamed Tarek

Runs every hour. Covers ONLY the Ingestion + Warehouse(Bronze) part of
the pipeline for now:

  0) create_topic.py             -> makes sure the Kafka topic exists
  1) producer_live.py            -> publishes the current hour's reading
                                     for every at-risk city to Kafka
  2) kafka_to_bronze_consumer.py -> reads those messages and writes them,
                                     unmodified, into bronze.live_weather

NOTE: this DAG stops at Bronze on purpose. Once Youssef's Spark jobs
(Silver/Gold) and Abdelrahman's ML inference are ready, extend this DAG
(or chain a new one after it) rather than duplicating the schedule.
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/opt/airflow/project")

default_args = {
    "owner": "mohamed_tarek",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="hourly_ingestion",
    description="Hourly: publish live weather to Kafka, then write it into bronze.live_weather",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,   # يشتغل لوحده من غير ما تفعّله
    default_args=default_args,
    tags=["flood-warning", "ingestion", "hourly"],
) as dag:

    ensure_topic = BashOperator(
        task_id="ensure_topic",
        bash_command=f"cd {PROJECT_DIR} && /opt/uv-venv/bin/python ingestion/create_topic.py",
    )

    produce_live_reading = BashOperator(
        task_id="producer_live",
        bash_command=f"cd {PROJECT_DIR} && /opt/uv-venv/bin/python ingestion/producer_live.py",
    )

    write_to_bronze = BashOperator(
        task_id="kafka_to_bronze_consumer",
        bash_command=f"cd {PROJECT_DIR} && /opt/uv-venv/bin/python ingestion/kafka_to_bronze_consumer.py",
    )

    ensure_topic >> produce_live_reading >> write_to_bronze