"""Slack tells the incident channel about its origin, and the team about new partners."""

from __future__ import annotations

from typing import Any

import pytest

from firefighter.incidents.enums import IncidentOrigin
from firefighter.incidents.factories import IncidentFactory
from firefighter.incidents.models.partner import Partner
from firefighter.slack.factories import IncidentChannelFactory, SlackConversationFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentOriginUpdated,
    SlackMessagePartnerCreated,
)
from firefighter.slack.models.conversation import Conversation, ConversationStatus
from firefighter.slack.signals.incident_origin import (
    incident_origin_updated_handler,
    partner_created_handler,
)


@pytest.mark.django_db
class TestOriginMessage:
    @staticmethod
    def test_posted_in_the_incident_channel(mocker: Any) -> None:
        send = mocker.patch.object(Conversation, "send_message_and_save")
        algolia = Partner.objects.create(name="Algolia", slug="algolia")
        incident = IncidentFactory.create(
            origin=IncidentOrigin.PARTNER, partner=algolia
        )
        IncidentChannelFactory.create(
            incident=incident, _status=ConversationStatus.OPENED
        )
        incident.refresh_from_db()

        incident_origin_updated_handler(sender=None, incident=incident, user=None)

        message = send.call_args.args[0]
        assert isinstance(message, SlackMessageIncidentOriginUpdated)
        assert "Partner: Algolia" in message.get_text()

    @staticmethod
    def test_not_posted_in_an_archived_channel(mocker: Any) -> None:
        send = mocker.patch.object(Conversation, "send_message_and_save")
        incident = IncidentFactory.create()
        IncidentChannelFactory.create(
            incident=incident, _status=ConversationStatus.ARCHIVED
        )
        incident.refresh_from_db()

        incident_origin_updated_handler(sender=None, incident=incident, user=None)

        send.assert_not_called()


@pytest.mark.django_db
class TestNewPartnerMessage:
    @staticmethod
    def test_asks_the_team_to_review_it(mocker: Any) -> None:
        send = mocker.patch.object(Conversation, "send_message_and_save")
        SlackConversationFactory.create(tag="dev_firefighter")
        partner = Partner.objects.create(name="Zyte", slug="zyte", is_reviewed=False)
        incident = IncidentFactory.create()

        partner_created_handler(sender=None, partner=partner, incident=incident)

        message = send.call_args.args[0]
        assert isinstance(message, SlackMessagePartnerCreated)
        assert "Zyte" in message.get_text()
        assert f"/admin/incidents/partner/{partner.id}/change/" in message.get_text()
