"""Load hourly risk records from Silver into Gold."""

import logging
import sys
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from spark.jdbc_io import (  # noqa: E402
    create_spark_session,
    read_sql_table,
    write_sql_table,
)


logger = logging.getLogger("silver_to_gold_load")

SOURCE_TABLE = "silver.fact_weather_features"
TARGET_TABLE = "gold.fact_hourly_risk"

RISK_INPUT_COLUMNS = [
    "city",
    "event_time",
    "source",
    "precipitation",
    "rain_sum_1h",
    "rain_sum_3h",
    "rain_sum_6h",
    "rain_sum_24h",
    "rain_sum_72h",
    "soil_moisture_0_to_7cm",
    "elevation",
    "slope_degree",
]

#These refrences Match the md file "Yousef spark" اللي طارق بعته
NORMALIZATION_REFERENCES = {
    "rain_1h": 15.0,
    "rain_3h": 30.0,
    "rain_6h": 45.0,
    "rain_72h": 80.0,
    "soil_moisture": 0.5,
    "slope": 30.0,
}
ELEVATION_REFERENCE_METERS = 1600.0

# أسماء الأعمدة التي هنكتبها في Gold.
GOLD_OUTPUT_COLUMNS = [
    "city",
    "event_time",
    "avg_rainfall",
    "rain_sum_24h",
    "rain_sum_72h",
    "risk_score",
    "risk_level",
]


def _read_silver_features(spark: object) -> DataFrame:
    """Read and validate the Silver columns needed for hourly risk."""
    silver = read_sql_table(spark, SOURCE_TABLE)

    missing_columns = sorted(set(RISK_INPUT_COLUMNS) - set(silver.columns))
    if missing_columns:
        raise ValueError(
            "Silver table is missing required columns: "
            + ", ".join(missing_columns)
        )

    return (
        silver.select(*RISK_INPUT_COLUMNS)
        .withColumn("avg_rainfall", F.col("precipitation"))
        .dropDuplicates(["city", "event_time"])
    )


def _smooth_normalize(column_name: str, reference: float):
    """Convert a non-negative input to a smooth value between 0 and 1."""
    return F.lit(1.0) - F.exp(
        -F.col(column_name).cast("double") / F.lit(reference)
    )


def _calculate_risk_score(weather: DataFrame) -> DataFrame:
    """Calculate a 0-100 risk score using the project task formula."""
    normalized = (
        weather
        .withColumn(
            "_r1",
            _smooth_normalize(
                "rain_sum_1h",
                NORMALIZATION_REFERENCES["rain_1h"],
            ),
        )
        .withColumn(
            "_r3",
            _smooth_normalize(
                "rain_sum_3h",
                NORMALIZATION_REFERENCES["rain_3h"],
            ),
        )
        .withColumn(
            "_r6",
            _smooth_normalize(
                "rain_sum_6h",
                NORMALIZATION_REFERENCES["rain_6h"],
            ),
        )
        .withColumn(
            "_rain72",
            _smooth_normalize(
                "rain_sum_72h",
                NORMALIZATION_REFERENCES["rain_72h"],
            ),
        )
        .withColumn(
            "_soil",
            _smooth_normalize(
                "soil_moisture_0_to_7cm",
                NORMALIZATION_REFERENCES["soil_moisture"],
            ),
        )
        .withColumn(
            "_slope",
            _smooth_normalize(
                "slope_degree",
                NORMALIZATION_REFERENCES["slope"],
            ),
        )
        .withColumn(
            "_elevation_factor",
            F.exp(
                -F.col("elevation").cast("double")
                / F.lit(ELEVATION_REFERENCE_METERS)
            ),
        )
    )

    factors = (
        normalized
        .withColumn(
            "_rainfall_hazard",
            0.50 * F.col("_r1")
            + 0.30 * F.col("_r3")
            + 0.20 * F.col("_r6"),
        )
        .withColumn(
            "_antecedent_condition",
            0.60 * F.col("_rain72")
            + 0.40 * F.col("_soil"),
        )
        .withColumn(
            "_terrain",
            0.70 * F.col("_slope")
            + 0.30 * F.col("_elevation_factor"),
        )
    )

    return factors.withColumn(
        "risk_score",
        F.round(
            100
            * (
                0.60 * F.col("_rainfall_hazard")
                + 0.25 * F.col("_antecedent_condition")
                + 0.15 * F.col("_terrain")
            )
        ).cast("int"),
    )


def _derive_historical_thresholds(scored: DataFrame) -> dict[str, float]:
    """Find the P80, P95, and P99 risk-score percentiles from historical rows."""
    historical = scored.filter(F.col("source") == "historical")

    values = historical.approxQuantile(
        "risk_score",
        [0.80, 0.95, 0.99],
        0.001,
    )

    if len(values) != 3:
        raise ValueError(
            "Could not calculate risk thresholds: "
            "historical rows or risk scores are missing"
        )

    return {
        "p80": values[0],
        "p95": values[1],
        "p99": values[2],
    }


def _add_risk_level(
    scored: DataFrame,
    p80: float,
    p95: float,
    p99: float,
) -> DataFrame:
    """Assign a risk label using the historical percentile thresholds."""
    return scored.withColumn(
        "risk_level",
        F.when(F.col("risk_score") < p80, F.lit("آمن"))
        .when(F.col("risk_score") < p95, F.lit("مراقبة"))
        .when(F.col("risk_score") < p99, F.lit("خطر"))
        .otherwise(F.lit("خطر شديد")),
    )


def _read_existing_gold_keys(spark: object) -> DataFrame:
    """Read Gold keys so rerunning the job does not append the same hours again."""
    return (
        read_sql_table(spark, TARGET_TABLE)
        .select(
            "city",
            F.to_timestamp("event_time").alias("event_time"),
        )
        .dropDuplicates(["city", "event_time"])
    )


def run() -> None:
    """Calculate hourly risk from Silver and append new rows to Gold."""
    spark = create_spark_session("silver-to-gold-risk-load")

    try:
        logger.info("Reading Silver weather features")
        silver_weather = _read_silver_features(spark)

        logger.info("Calculating risk scores")
        scored_weather = _calculate_risk_score(silver_weather)

        logger.info("Calculating thresholds from historical rows")
        thresholds = _derive_historical_thresholds(scored_weather)
        logger.info(
            "Historical thresholds: P80=%s, P95=%s, P99=%s",
            thresholds["p80"],
            thresholds["p95"],
            thresholds["p99"],
        )

        classified_weather = _add_risk_level(
            scored_weather,
            thresholds["p80"],
            thresholds["p95"],
            thresholds["p99"],
        )

        gold_rows = classified_weather.select(*GOLD_OUTPUT_COLUMNS)

        logger.info("Checking which city-hour rows already exist in Gold")
        existing_keys = _read_existing_gold_keys(spark)

        new_gold_rows = (
            gold_rows
            .withColumn("event_time", F.to_timestamp("event_time"))
            .join(
                existing_keys,
                on=["city", "event_time"],
                how="left_anti",
            )
        )

        if not new_gold_rows.take(1):
            logger.info("No new rows to write to Gold")
            return

        logger.info("Appending new hourly risk rows to Gold")
        write_sql_table(new_gold_rows, TARGET_TABLE)

        logger.info("Silver to Gold risk load finished successfully")

    finally:
        spark.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run()