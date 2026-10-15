"""Incremental job that transforms new live Bronze rows into Silver."""

import logging
import sys
from pathlib import Path
from pyspark.sql import functions as F

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from spark.jdbc_io import (  # noqa: E402
    create_spark_session,
    read_sql_table,
    write_sql_table,
)
from spark.shared_feature_logic import (  # noqa: E402
    SILVER_FEATURE_COLUMNS,
    add_time_features,
    assert_all_locations_mapped,
    clean_bronze_weather,
    enrich_with_location,
)


logger = logging.getLogger("live_incremental_job")


#import columns from silver (context_columns) will need them to calc rainfall and time features
TIME_CONTEXT_COLUMNS = [
    "city",
    "event_time",
    "source",
    "precipitation",
    "relative_humidity_2m",
    "temperature_2m",
    "surface_pressure",
    "windspeed_10m",
    "cloudcover",
    "soil_moisture_0_to_7cm",
    "elevation",
    "slope_degree",
]


def _build_time_context(spark, new_rows):
    """Add the previous 71 hours from Silver for each new live row"""
    new_keys = (
        new_rows.select(
            "city",
            F.to_timestamp("event_time").alias("event_time"),
        )
        .dropDuplicates(["city", "event_time"])
    )

    silver_context = (
        read_sql_table(spark, "silver.fact_weather_features")
        .select(*TIME_CONTEXT_COLUMNS)
        .withColumn("event_time", F.to_timestamp("event_time"))
    )

    context = silver_context.alias("context")
    keys = new_keys.alias("keys")

    context_time = F.col("context.event_time").cast("long")
    new_time = F.col("keys.event_time").cast("long")

    recent_silver_rows = (
        context.join(
            keys,
            on=(
                (F.col("context.city") == F.col("keys.city"))
                & (context_time >= new_time - F.lit(71 * 60 * 60))
                & (context_time <= new_time)
            ),
            how="inner",
        )
        .select(
            *[
                F.col(f"context.{column}").alias(column)
                for column in TIME_CONTEXT_COLUMNS
            ]
        )
    )

    new_rows_for_features = new_rows.select(*TIME_CONTEXT_COLUMNS)

    return (
        recent_silver_rows
        .unionByName(new_rows_for_features)
        .dropDuplicates(["city", "event_time"])
    )

def _read_new_live_rows(spark):
    """Read live Bronze rows whose city and event time are not in Silver yet."""
    live_rows = (
        read_sql_table(spark, "bronze.live_weather")
        .filter("source = 'live'")
        .withColumn("event_time", F.to_timestamp("event_time"))
        .dropDuplicates(["city", "event_time"])
    )

    silver_keys = (
        read_sql_table(spark, "silver.fact_weather_features")
        .select(
            "city",
            F.to_timestamp("event_time").alias("event_time"),
        )
        .dropDuplicates(["city", "event_time"])
    )

    return live_rows.join(
        silver_keys,
        on=["city", "event_time"],
        how="left_anti",
    )


def run() -> None:
    """Execute live Bronze -> Silver processing."""
    spark = create_spark_session("live-incremental")

    try:
        logger.info("Reading new live Bronze rows")
        new_live_rows = _read_new_live_rows(spark)

        if not new_live_rows.take(1):
            logger.info("No new live rows to process")
            return

        logger.info("Reading the location dimension")
        locations = read_sql_table(spark, "gold.dim_location")

        logger.info("Cleaning and enriching new live rows")
        clean_weather = clean_bronze_weather(new_live_rows)
        enriched_weather = enrich_with_location(clean_weather, locations)
        assert_all_locations_mapped(enriched_weather)

        time_context = _build_time_context(spark, enriched_weather)

        calculated_features = add_time_features(time_context)

        new_keys = (
            enriched_weather.select("city", "event_time")
            .dropDuplicates(["city", "event_time"])
        )

        silver_features = (
            calculated_features.join(
                new_keys,
                on=["city", "event_time"],
                how="left_semi",
            )
            .select(*SILVER_FEATURE_COLUMNS)
        )

        logger.info("Appending new live features to Silver")
        write_sql_table(silver_features, "silver.fact_weather_features")
        logger.info("Live incremental job finished successfully")

    finally:
        spark.stop()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run()