"""
dag_historical_bootstrap.py
Owner: Mohamed Tarek (orchestrates his own ingestion scripts + Mina's setup_db.py)

ONE-TIME DAG — not scheduled (schedule=None). Trigger it manually once,
right after Airflow itself is up, to set up the whole project from zero:

  1) setup_db.py            -> creates FloodProjectDB + Bronze/Silver/Gold tables
                                (safe to re-run — every .sql file is idempotent)
  2) fetch_static_data.py   -> gold.dim_location
  3) fetch_historical.py    -> bronze.historical_weather

Trigger manually from the Airflow UI (http://localhost:8080), or:
    airflow dags trigger historical_bootstrap
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Resolves to the project root automatically, regardless of whose
# machine this runs on: orchestration/dags/<this file> -> project root
# is two directories up.
PROJECT_DIR = os.environ.get("PROJECT_DIR", "/opt/airflow/project")

default_args = {
    "owner": "mohamed_tarek",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="historical_bootstrap",
    description="One-time: create DB/tables, then populate gold.dim_location and bronze.historical_weather",
    schedule=None,          # manual trigger only — this must never run twice carelessly
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["flood-warning", "warehouse", "ingestion", "one-time"],
) as dag:

    setup_database = BashOperator(
        task_id="setup_db",
        bash_command=f"cd {PROJECT_DIR} && /opt/uv-venv/bin/python warehouse/setup_db.py",
    )

    fetch_static_data = BashOperator(
        task_id="fetch_static_data",
        bash_command=f"cd {PROJECT_DIR} && /opt/uv-venv/bin/python ingestion/fetch_static_data.py",
    )

    fetch_historical = BashOperator(
        task_id="fetch_historical",
        bash_command=f"cd {PROJECT_DIR} && /opt/uv-venv/bin/python ingestion/fetch_historical.py",
        execution_timeout=timedelta(hours=3),
        retries=2,
        retry_delay=timedelta(minutes=10),
    )

    # Tables must exist before anything tries to write to them.
    # Static data runs before historical since it is the simpler, faster
    # call — if it fails, we find out before spending minutes pulling
    # 5 years of historical data.
    setup_database >> fetch_static_data >> fetch_historical