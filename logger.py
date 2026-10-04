"""
logger.py
Shared logging utility — used by everyone on the team instead of print().

Each script gets its own log file under logs/<script_name>.log, with
automatic rotation so log files never grow without limit.

Usage:
    from logger import get_logger
    logger = get_logger("fetch_static_data")

    logger.info("Starting...")
    logger.warning("Something looks off")
    logger.error("Request failed", exc_info=True)   # include traceback
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Returns a logger that writes ONLY to logs/<name>.log (no console output).
    Safe to call multiple times with the same name — won't duplicate handlers.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False 

    log_file = os.path.join(LOG_DIR, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(file_handler)

    return logger