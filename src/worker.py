"""Render worker entrypoint for the Strat scanner."""
import logging
import time

from .config import get_settings
from .data_providers import MassiveClient
from .logging_utils import configure_logging
from .scanner import Scanner

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the Strat scanner loop."""
    configure_logging()
    settings = get_settings()
    logger.info("Starting Strat scanner worker", extra={"env": settings.ENVIRONMENT})

    client = MassiveClient()
    scanner = Scanner(client)

    while True:
        try:
            scanner.scan_once()
        except Exception:
            logger.exception("Unhandled error during scan loop")
        time.sleep(settings.SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Worker interrupted; shutting down gracefully")
