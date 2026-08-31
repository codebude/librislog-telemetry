"""
Logging configuration for librislog-telemetry.

Call configure_logging() once at application startup (app/main.py).
Every other module obtains its logger with:

    import logging
    logger = logging.getLogger(__name__)
"""

import logging

_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root 'app' logger and the console handler.

    uvicorn configures its own loggers separately; we leave those untouched so
    we don't end up with duplicate access-log lines.

    Args:
        level: Log level string (e.g. "INFO", "DEBUG"). Defaults to "INFO".
    """
    numeric = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(numeric)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    app_logger = logging.getLogger("app")
    app_logger.setLevel(numeric)
    if not app_logger.handlers:
        app_logger.addHandler(handler)
    else:
        app_logger.handlers[0].setLevel(numeric)

    logging.getLogger("app").info("Logging configured at level %s", level.upper())
