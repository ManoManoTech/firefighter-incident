from __future__ import annotations

import pytest


def test_json_logging(caplog: pytest.LogCaptureFixture, capsys, settings) -> None:
    """This test ensures that JSON logging is working."""
    # ruff: noqa: PLC0415
    import logging

    from firefighter.firefighter.settings.components.logging import (
        get_json_formatter,
    )

    caplog.set_level(logging.INFO)
    # Override the current logging settings
    settings.LOGGING["formatters"]["dynamicfmt"] = get_json_formatter()

    from logging import config

    config.dictConfig(settings.LOGGING)
    logger = logging.getLogger(__name__)

    logger.info("Testing now.")

    captured = capsys.readouterr()
    assert '{"message": "Testing now.",' in captured.err
    # XXX Make more testing assertion about our expected JSON log output and its format.
    # This is a bit tricky as it is in Gunicorn logs.
