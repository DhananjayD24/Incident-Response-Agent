"""
JSON structured logger for the order-service.
Every log record includes: timestamp, level, endpoint, status, duration_ms, error_type.
"""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.config import settings


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("order_service")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = _build_logger()
