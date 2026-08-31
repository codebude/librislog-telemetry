"""
Logging configuration for librislog-telemetry.

Call configure_logging() once at application startup (app/main.py).
Every other module obtains its logger with:

    import logging
    logger = logging.getLogger(__name__)

Privacy note: the uvicorn access log (which records the client IP on every
request) is disabled via ``--no-access-log``. As a second layer, the formatter
below masks the trailing octets of any IPv4 address that slips through, e.g.
slowapi's rate-limit warnings. The leading octets stay visible (controlled by
``mask_octets``) so a repeat offender can still be recognised as the same host
while its full address stays anonymous.
"""

import logging
import re

_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%S"

_IP_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)


def _mask_ip(match: re.Match[str], mask_octets: int) -> str:
    """Replace the trailing *mask_octets* octets of an IP with ``x``."""
    octets = match.group(0).split(".")
    kept = octets[: 4 - mask_octets]
    return ".".join(kept + ["x"] * mask_octets)


class MaskIpFormatter(logging.Formatter):
    """Formatter that masks the trailing octets of IPv4 addresses in messages."""

    def __init__(self, fmt: str | None = None, *, mask_octets: int = 1) -> None:
        super().__init__(fmt=fmt)
        self.mask_octets = max(1, min(mask_octets, 4))

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return _IP_PATTERN.sub(lambda m: _mask_ip(m, self.mask_octets), message)


def configure_logging(level: str = "INFO", *, mask_octets: int = 1) -> None:
    """Configure the root 'app' logger and the console handler.

    The uvicorn access log is disabled separately via ``--no-access-log``.
    This function only configures the ``app`` logger and the ``slowapi``
    logger (so rate-limit warnings stay visible but IP-masked).

    Args:
        level: Log level string (e.g. "INFO", "DEBUG"). Defaults to "INFO".
        mask_octets: Number of trailing IPv4 octets to mask. Defaults to 1.
    """
    numeric = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(numeric)
    handler.setFormatter(MaskIpFormatter(_FORMAT, mask_octets=mask_octets))

    app_logger = logging.getLogger("app")
    app_logger.setLevel(numeric)
    if not app_logger.handlers:
        app_logger.addHandler(handler)
    else:
        app_logger.handlers[0].setLevel(numeric)

    slowapi_logger = logging.getLogger("slowapi")
    slowapi_logger.setLevel(logging.WARNING)
    slowapi_logger.handlers = [handler]
    slowapi_logger.propagate = False

    logging.getLogger("app").info("Logging configured at level %s", level.upper())