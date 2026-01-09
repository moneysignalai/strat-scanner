"""Logging configuration helpers."""
import logging

from .config import get_settings


def configure_logging() -> None:
    """Configure root logging based on settings."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.DEBUG_MODE in (True, "true", "True", "1"):
        fmt = "%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s"
    else:
        fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
    )
