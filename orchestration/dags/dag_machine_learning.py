import os
from datetime import datetime, timedelta
import pendulum
from airflow.decorators import dag, task

PROJECT_DIR = os.environ.get(
    "PROJECT_DIR",
    "/opt/airflow/project",
)

PYTHON = os.environ.get(
    "ML_PYTHON",
    "/opt/uv-venv/env/bin/python",
)

ML_DIR = f"{PROJECT_DIR}/ml"

default_args = {
    "owner": "mohamed_tarek",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}


@dag(
    dag_id="ml_inference",
    description="Run ML inference and save predictions",
    schedule="0 * * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Africa/Cairo"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["machine-learning", "inference"],
)
def ml_inference():
    @task.bash(execution_timeout=timedelta(minutes=20))
    def run_inference() -> str:
        return (
            "set -euo pipefail; "
            f"cd {ML_DIR} && "
            f"{PYTHON} inference_job.py"
        )

    run_inference()


@dag(
    dag_id="ml_retraining",
    description="Train a candidate model and evaluate it",
    schedule=timedelta(days=14),
    start_date=pendulum.datetime(2026, 1, 1, tz="Africa/Cairo"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["machine-learning", "retraining"],
)
def ml_retraining():
    @task.bash(execution_timeout=timedelta(hours=3))
    def train_candidate() -> str:
        return (
            "set -euo pipefail; "
            f"cd {ML_DIR} && "
            f"{PYTHON} train_model.py"
        )

    @task.bash(execution_timeout=timedelta(hours=1))
    def evaluate_and_promote() -> str:
        return (
            "set -euo pipefail; "
            f"cd {ML_DIR} && "
            f"{PYTHON} retrain_job.py"
        )

    train_candidate() >> evaluate_and_promote()


ml_inference()
ml_retraining()
