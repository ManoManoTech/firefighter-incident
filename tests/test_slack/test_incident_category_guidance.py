"""The guidance set on an incident category is posted in the channel of P1-P3 incidents."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError

from firefighter.incidents.factories import (
    IncidentCategoryFactory,
    IncidentFactory,
    UserFactory,
)
from firefighter.incidents.models import Priority
from firefighter.incidents.models.incident_category import (
    CHANNEL_GUIDANCE_MAX_LENGTH,
    IncidentCategory,
)
from firefighter.slack.factories import IncidentChannelFactory
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentCategoryGuidance,
)
from firefighter.slack.rules import should_post_category_guidance
from firefighter.slack.signals.create_incident_conversation import (
    create_incident_slack_conversation,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from firefighter.incidents.models.incident import Incident

GUIDANCE = "Runbook: <https://example.test/runbook|Payment runbook>"


def _category(guidance: str = GUIDANCE) -> IncidentCategory:
    return IncidentCategoryFactory.create(name="Payment", channel_guidance=guidance)


def _incident(priority_value: int, category: IncidentCategory | None = None) -> Incident:
    return IncidentFactory.create(
        priority=Priority.objects.get(value=priority_value),
        incident_category=category or _category(),
    )


def _guidance_posts(mock_send: MagicMock) -> list[SlackMessageIncidentCategoryGuidance]:
    return [
        call.args[0]
        for call in mock_send.call_args_list
        if isinstance(call.args[0], SlackMessageIncidentCategoryGuidance)
    ]


@pytest.mark.django_db
class TestShouldPostCategoryGuidance:
    @staticmethod
    @pytest.mark.parametrize("priority_value", [1, 2, 3])
    def test_posted_for_p1_to_p3(priority_value: int) -> None:
        assert should_post_category_guidance(_incident(priority_value)) is True

    @staticmethod
    @pytest.mark.parametrize("priority_value", [4, 5])
    def test_not_posted_for_p4_and_p5(priority_value: int) -> None:
        assert should_post_category_guidance(_incident(priority_value)) is False

    @staticmethod
    @pytest.mark.parametrize("guidance", ["", "  \n "])
    def test_not_posted_without_guidance(guidance: str) -> None:
        assert should_post_category_guidance(_incident(1, _category(guidance))) is False


@pytest.mark.django_db
class TestGuidanceMessage:
    @staticmethod
    def test_shows_the_category_and_its_guidance() -> None:
        blocks = SlackMessageIncidentCategoryGuidance(_incident(1)).get_blocks()

        (block,) = blocks
        text = block.to_dict()["text"]["text"]
        assert text.startswith(":books: *Useful information for Payment incidents*\n")
        assert text.endswith(GUIDANCE)

    @staticmethod
    def test_longest_guidance_fits_in_one_slack_section() -> None:
        category = IncidentCategoryFactory.create(
            name="n" * 128,  # IncidentCategory.name max_length
            channel_guidance="x" * CHANNEL_GUIDANCE_MAX_LENGTH,
        )

        (block,) = SlackMessageIncidentCategoryGuidance(
            _incident(1, category)
        ).get_blocks()

        assert len(block.to_dict()["text"]["text"]) <= 3000

    @staticmethod
    def test_admin_rejects_a_guidance_too_long_for_slack() -> None:
        # A TextField's max_length is enforced by its form field, the one the admin uses
        form_field = IncidentCategory._meta.get_field("channel_guidance").formfield()

        form_field.clean("x" * CHANNEL_GUIDANCE_MAX_LENGTH)
        with pytest.raises(ValidationError):
            form_field.clean("x" * (CHANNEL_GUIDANCE_MAX_LENGTH + 1))


@pytest.mark.django_db
class TestPostedWhenTheChannelOpens:
    @staticmethod
    def _open_channel(mocker: MockerFixture, incident: Incident) -> MagicMock:
        new_channel = MagicMock()
        new_channel.channel_id = "C0NEWCHANNEL"
        mocker.patch(
            "firefighter.slack.signals.create_incident_conversation.IncidentChannel.objects.create_incident_channel",
            return_value=new_channel,
        )
        mocker.patch.object(incident, "build_invite_list", return_value=[])
        mocker.patch(
            "firefighter.slack.signals.create_incident_conversation.should_publish_in_general_channel",
            return_value=False,
        )
        mocker.patch(
            "firefighter.slack.signals.create_incident_conversation.should_publish_in_it_deploy_channel",
            return_value=False,
        )
        mocker.patch.object(type(incident), "conversation", new_channel, create=True)

        create_incident_slack_conversation(incident=incident)
        return new_channel

    def test_posted_and_pinned_after_the_announcement(self, mocker: MockerFixture) -> None:
        channel = self._open_channel(mocker, _incident(2))

        sent = [call.args[0].id for call in channel.send_message_and_save.call_args_list]
        assert sent.index(SlackMessageIncidentCategoryGuidance.id) == 1
        (post,) = [
            call
            for call in channel.send_message_and_save.call_args_list
            if isinstance(call.args[0], SlackMessageIncidentCategoryGuidance)
        ]
        assert post.kwargs == {"pin": True}

    def test_not_posted_without_guidance(self, mocker: MockerFixture) -> None:
        channel = self._open_channel(mocker, _incident(2, _category("")))

        assert _guidance_posts(channel.send_message_and_save) == []


@pytest.mark.django_db
class TestPostedWhenItStartsToApply:
    @staticmethod
    def _with_channel(incident: Incident, mocker: MockerFixture) -> MagicMock:
        conversation = IncidentChannelFactory.create(incident=incident)
        return mocker.patch.object(conversation, "send_message_and_save")

    @staticmethod
    def test_posted_when_the_incident_moves_to_the_category(
        mocker: MockerFixture,
    ) -> None:
        incident = _incident(2, _category(""))
        mock_send = TestPostedWhenItStartsToApply._with_channel(incident, mocker)
        new_category = IncidentCategoryFactory.create(
            name="Checkout", channel_guidance=GUIDANCE
        )

        incident.create_incident_update(
            created_by=UserFactory.create(), incident_category_id=new_category.id
        )

        (post,) = _guidance_posts(mock_send)
        assert "Checkout" in post.get_text()

    @staticmethod
    def test_posted_when_escalated_to_p1_to_p3_with_a_channel(
        mocker: MockerFixture,
    ) -> None:
        incident = _incident(4)
        mock_send = TestPostedWhenItStartsToApply._with_channel(incident, mocker)

        incident.create_incident_update(
            created_by=UserFactory.create(),
            priority_id=Priority.objects.get(value=2).id,
        )

        assert len(_guidance_posts(mock_send)) == 1

    @staticmethod
    def test_not_reposted_within_p1_to_p3(mocker: MockerFixture) -> None:
        incident = _incident(3)
        mock_send = TestPostedWhenItStartsToApply._with_channel(incident, mocker)

        incident.create_incident_update(
            created_by=UserFactory.create(),
            priority_id=Priority.objects.get(value=1).id,
        )

        assert _guidance_posts(mock_send) == []

    @staticmethod
    def test_not_posted_when_moving_a_p4_to_another_category(
        mocker: MockerFixture,
    ) -> None:
        incident = _incident(4, _category(""))
        mock_send = TestPostedWhenItStartsToApply._with_channel(incident, mocker)

        incident.create_incident_update(
            created_by=UserFactory.create(), incident_category_id=_category().id
        )

        assert _guidance_posts(mock_send) == []

    @staticmethod
    def test_not_posted_for_other_updates(mocker: MockerFixture) -> None:
        incident = _incident(2)
        mock_send = TestPostedWhenItStartsToApply._with_channel(incident, mocker)

        incident.create_incident_update(
            created_by=UserFactory.create(), message="Still investigating the cause"
        )

        assert _guidance_posts(mock_send) == []
