from __future__ import annotations

from django.utils.timezone import datetime, get_current_timezone

from firefighter.confluence.utils import (
    CONFLUENCE_PM_ARCHIVE_TITLE_REGEX,
    CONFLUENCE_PM_TITLE_REGEX,
    parse_postmortem_title,
)


def test_postmortem_parsing_regex() -> None:
    assert (
        CONFLUENCE_PM_TITLE_REGEX.match("#20200808-inc-123 (SEV-1) This is a title")
        is not None
    )
    assert CONFLUENCE_PM_TITLE_REGEX.match("TODO: Make a postmortem") is None
    assert CONFLUENCE_PM_TITLE_REGEX.match("[ARCHIVE] Q1 2032") is None

    valid_old = "#20200808-inc-123 (SEV-1) This is a title"
    r = CONFLUENCE_PM_TITLE_REGEX.match(valid_old)
    assert r is not None
    assert r.groupdict() == {
        "date": "20200808-inc",
        "id": "123",
        "priority": "(SEV-1)",
        "title": "This is a title",
    }

    valid_recent = "#20200808-123-abc (SEV1) This is a title"
    r = CONFLUENCE_PM_TITLE_REGEX.match(valid_recent)
    assert r is not None
    assert r.groupdict() == {
        "date": "20200808",
        "id": "123",
        "priority": "(SEV1)",
        "title": "This is a title",
    }


def test_postmortem_title_parsing() -> None:
    assert parse_postmortem_title("#20200808-inc-123 (SEV-1) This is a title") == (
        datetime(2020, 8, 8, tzinfo=get_current_timezone()),
        "2020Q3",
    )


def test_postmortem_archive_title_regex() -> None:
    assert CONFLUENCE_PM_ARCHIVE_TITLE_REGEX.match("[Archive] Q1 2032") is not None
    assert CONFLUENCE_PM_ARCHIVE_TITLE_REGEX.match("Q3 2032") is not None
    assert (
        CONFLUENCE_PM_ARCHIVE_TITLE_REGEX.match("[Template] FireFighter template")
        is None
    )
    assert (
        CONFLUENCE_PM_ARCHIVE_TITLE_REGEX.match(
            "#20200808-inc-123 (SEV-1) This is a title"
        )
        is None
    )
