"""Tests for logging configuration and IP masking."""

import logging

from app.logging_config import MaskIpFormatter, configure_logging


def test_mask_last_octet_only():
    formatter = MaskIpFormatter("%(message)s", mask_octets=1)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="rate limit exceeded from 192.168.1.10",
        args=(),
        exc_info=None,
    )
    assert formatter.format(record) == "rate limit exceeded from 192.168.1.x"


def test_mask_last_two_octets():
    formatter = MaskIpFormatter("%(message)s", mask_octets=2)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="rate limit exceeded from 192.168.1.10",
        args=(),
        exc_info=None,
    )
    assert formatter.format(record) == "rate limit exceeded from 192.168.x.x"


def test_mask_preserves_prefix_for_repeat_identification():
    """Same prefix, different host — still identifiable as same network."""
    formatter = MaskIpFormatter("%(message)s", mask_octets=1)
    a = logging.LogRecord("t", logging.INFO, __file__, 1, "from 10.0.0.5", (), None)
    b = logging.LogRecord("t", logging.INFO, __file__, 1, "from 10.0.0.9", (), None)
    assert formatter.format(a) == "from 10.0.0.x"
    assert formatter.format(b) == "from 10.0.0.x"


def test_mask_multiple_ips_and_ports():
    formatter = MaskIpFormatter("%(message)s", mask_octets=1)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="client 10.0.0.5 and 172.16.0.9:8080 seen",
        args=(),
        exc_info=None,
    )
    assert formatter.format(record) == "client 10.0.0.x and 172.16.0.x:8080 seen"


def test_leave_non_ip_text_untouched():
    formatter = MaskIpFormatter("%(message)s", mask_octets=1)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="New installation registered: inst-001",
        args=(),
        exc_info=None,
    )
    assert formatter.format(record) == "New installation registered: inst-001"


def test_configure_logging_wires_slowapi_logger():
    configure_logging("INFO", mask_octets=2)
    slowapi_logger = logging.getLogger("slowapi")
    assert slowapi_logger.level == logging.WARNING
    assert slowapi_logger.propagate is False
    assert slowapi_logger.handlers, "slowapi logger should have a handler"
    assert isinstance(slowapi_logger.handlers[0].formatter, MaskIpFormatter)
    assert slowapi_logger.handlers[0].formatter.mask_octets == 2