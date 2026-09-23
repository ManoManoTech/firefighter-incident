"""Tests for `Incident.confluence_postmortem`.

The Confluence models are imported even when the app is not installed, so the
`postmortem_for` reverse relation exists while its table is never migrated.
Reading it directly would query a missing table.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist

from firefighter.api.serializers import IncidentSerializer
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models.incident import Incident
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentDeclaredAnnouncement,
    SlackMessageIncidentPostMortemCreated,
    SlackMessageIncidentPostMortemCreatedAnnouncement,
    SlackMessageIncidentProcessReminderAnnouncement,
)
from firefighter.slack.models.incident_channel import IncidentChannel
from firefighter.slack.signals.postmortem_created import postmortem_created_send
from firefighter.slack.views import CloseModal
from firefighter.slack.views.modals.postmortem import PostMortemModal


@pytest.mark.django_db
class TestConfluencePostmortem:
    def test_none_without_query_when_confluence_is_not_installed(
        self, django_assert_num_queries
    ) -> None:
        assert not apps.is_installed("firefighter.confluence")
        incident = IncidentFactory.create()

        with django_assert_num_queries(0):
            assert incident.confluence_postmortem is None

    def test_returns_the_postmortem_when_confluence_is_installed(self) -> None:
        incident = IncidentFactory.create()
        postmortem = MagicMock()

        with (
            patch.object(apps, "is_installed", return_value=True),
            patch.object(
                Incident, "postmortem_for", new_callable=PropertyMock
            ) as postmortem_for,
        ):
            postmortem_for.return_value = postmortem
            assert incident.confluence_postmortem is postmortem

    def test_none_when_confluence_is_installed_without_postmortem(self) -> None:
        incident = IncidentFactory.create()

        with (
            patch.object(apps, "is_installed", return_value=True),
            patch.object(
                Incident, "postmortem_for", new_callable=PropertyMock
            ) as postmortem_for,
        ):
            postmortem_for.side_effect = ObjectDoesNotExist
            assert incident.confluence_postmortem is None

    def test_declared_announcement_renders_without_confluence(self) -> None:
        """Regression: the announcement used to query the missing Confluence table."""
        incident = IncidentFactory.create()

        blocks = SlackMessageIncidentDeclaredAnnouncement(incident).get_blocks()

        assert blocks
        assert ":confluence:" not in str(blocks)


CONFLUENCE_PM = SimpleNamespace(
    page_url="https://confluence.example.com/pm",
    page_edit_url="https://confluence.example.com/pm/edit",
)


@pytest.fixture
def with_confluence_pm():
    with patch.object(
        Incident,
        "confluence_postmortem",
        new_callable=PropertyMock,
        return_value=CONFLUENCE_PM,
    ):
        yield CONFLUENCE_PM


@pytest.mark.django_db
@pytest.mark.usefixtures("with_confluence_pm")
class TestConfluencePostmortemLinks:
    """Every consumer links the Confluence post-mortem when there is one."""

    def test_postmortem_created_text(self) -> None:
        incident = IncidentFactory.create()

        text = SlackMessageIncidentPostMortemCreated(incident).get_text()

        assert f"• Confluence: {CONFLUENCE_PM.page_url}" in text

    def test_postmortem_created_announcement(self) -> None:
        incident = IncidentChannelFactory.create().incident

        blocks = SlackMessageIncidentPostMortemCreatedAnnouncement(
            incident
        ).get_blocks()

        assert CONFLUENCE_PM.page_url in str(blocks)

    def test_process_reminder_announcement(self) -> None:
        incident = IncidentChannelFactory.create().incident

        blocks = SlackMessageIncidentProcessReminderAnnouncement(incident).get_blocks()

        assert CONFLUENCE_PM.page_url in str(blocks)

    def test_close_modal_links_the_postmortem(self) -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        with patch.object(
            Incident,
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(True, []),
        ):
            view = CloseModal().build_modal_fn(body={}, incident=incident)

        assert CONFLUENCE_PM.page_url in str(view.to_dict())

    def test_close_modal_asks_to_fill_the_postmortem(self, settings) -> None:
        settings.ENABLE_CONFLUENCE = True
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        with patch.object(
            Incident,
            "can_be_closed",
            new_callable=PropertyMock,
            return_value=(False, [("STATUS_NOT_POST_MORTEM", "Not in post-mortem")]),
        ):
            view = CloseModal().build_modal_fn(body={}, incident=incident)

        assert CONFLUENCE_PM.page_edit_url in str(view.to_dict())

    def test_postmortem_modal_links_the_postmortem(self) -> None:
        incident = SimpleNamespace(
            id=1,
            confluence_postmortem=CONFLUENCE_PM,
            needs_postmortem=True,
            status=IncidentStatus.MITIGATED,
        )

        with patch(
            "firefighter.slack.views.modals.postmortem._safe_has_relation",
            return_value=False,
        ):
            view = PostMortemModal().build_modal_fn(incident)

        assert f"<{CONFLUENCE_PM.page_url}|View page>" in str(view.to_dict())

    def test_postmortem_created_bookmarks_the_postmortem(self) -> None:
        incident = IncidentChannelFactory.create().incident

        with (
            patch.object(IncidentChannel, "send_message_and_save"),
            patch.object(IncidentChannel, "add_bookmark") as add_bookmark,
        ):
            postmortem_created_send(sender=None, incident=incident)

        add_bookmark.assert_called_once_with(
            title="Postmortem (Confluence)",
            link=CONFLUENCE_PM.page_url,
            emoji=":confluence:",
        )

    def test_api_postmortem_url(self) -> None:
        incident = IncidentFactory.create()

        assert IncidentSerializer.get_postmortem_url(incident) == CONFLUENCE_PM.page_url


@pytest.mark.django_db
def test_api_postmortem_url_without_confluence() -> None:
    assert IncidentSerializer.get_postmortem_url(IncidentFactory.create()) is None
