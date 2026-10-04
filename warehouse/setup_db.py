import re
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from warehouse.db_connection import get_raw_connection
from logger import get_logger

logger = get_logger("setup_db")

SQL_DIR = Path(__file__).parent / "sql"

SQL_FILES_IN_ORDER = [
    "create_db.sql",
    "create_bronze_tables.sql",
    "create_silver_table.sql",
    "create_gold_tables.sql",
]


def split_into_batches(sql_text: str) -> list[str]:
    """
    T-SQL scripts use 'GO' as a batch separator, which is a convention
    understood by sqlcmd/SSMS only — not real SQL. pyodbc needs each
    batch executed separately, so split on any line that is just 'GO'.
    """
    batches = re.split(r"^\s*GO\s*$", sql_text, flags=re.IGNORECASE | re.MULTILINE)
    return [b.strip() for b in batches if b.strip()]


def run_sql_file(conn, filename: str):
    path = SQL_DIR / filename
    sql_text = path.read_text(encoding="utf-8")
    batches = split_into_batches(sql_text)

    cursor = conn.cursor()
    for i, batch in enumerate(batches, start=1):
        try:
            cursor.execute(batch)
        except Exception:
            logger.error(f"Failed executing batch {i}/{len(batches)} from {filename}", exc_info=True)
            raise
    logger.info(f"Executed {filename} ({len(batches)} batches)")


if __name__ == "__main__":
    logger.info("setup_db.py started")

    # Connect to "master" — FloodProjectDB might not exist yet on a fresh
    # machine, and CREATE DATABASE must run outside an explicit transaction.
    conn = get_raw_connection(database="master", autocommit=True)

    try:
        for filename in SQL_FILES_IN_ORDER:
            run_sql_file(conn, filename)
        logger.info("setup_db.py finished successfully — database and all tables are ready")
        print("✅ Database and all tables (Bronze, Silver, Gold) are ready.")
    except Exception as e:
        logger.error("setup_db.py failed", exc_info=True)
        print(f"❌ Setup failed: {e}. Check logs/setup_db.log for the full traceback.")
        raise
    finally:
        conn.close()