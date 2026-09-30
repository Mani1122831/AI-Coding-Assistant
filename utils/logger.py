"""
utils/logger.py
Centralised logging configuration.
Logs technical details without exposing secrets.
"""
import logging
import sys
from typing import Optional

from config.settings import settings


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.
    Log level is controlled by the LOG_LEVEL environment variable.
    """
    logger = logging.getLogger(name)

    # Only configure if handlers haven't been added yet
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    # Prevent messages from propagating to the root logger twice
    logger.propagate = False

    return logger
