"""Tests for DowngradeWorkflowModal - switch a downgraded incident to the Jira-ticket workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, PropertyMock

import pytest

from firefighter.incidents.enums import DOWNGRADE_WORKFLOW_EVENT_TYPE, IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import (
    COMMANDER_ROLE_SLUG,
    IncidentRoleType,
)
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory
from firefighter.slack.views.modals.downgrade_workflow import (
    DowngradeWorkflowModal,
    can_switch_workflow,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User


def _give_command(incident: Incident, user: User) -> None:
    IncidentRole.objects.create(
        incident=incident,
        user=user,
        role_type=IncidentRoleType.objects.get(slug=COMMANDER_ROLE_SLUG),
    )


@pytest.mark.django_db
class TestCanSwitchWorkflow:
    @staticmethod
    def test_anyone_may_switch_without_a_commander() -> None:
        incident = IncidentFactory.create()

        assert can_switch_workflow(incident, UserFactory.create())

    @staticmethod
    def test_commander_may_switch() -> None:
        incident = IncidentFactory.create()
        commander = UserFactory.create()
        _give_command(incident, commander)

        assert can_switch_workflow(incident, commander)

    @staticmethod
    def test_other_users_may_not_switch() -> None:
        incident = IncidentFactory.create()
        _give_command(incident, UserFactory.create())

        assert not can_switch_workflow(incident, UserFactory.create())
        assert not can_switch_workflow(incident, None)


@pytest.mark.django_db
class TestDowngradeWorkflowModalBuild:
    @staticmethod
    def test_commander_gets_the_submit_button() -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATING)
        IncidentChannelFactory.create(incident=incident)
        commander = UserFactory.create()
        _give_command(incident, commander)

        view = DowngradeWorkflowModal().build_modal_fn(incident=incident, user=commander)

        assert view.submit is not None
        assert "still open on its" in str(view.blocks[1].text.text)

    @staticmethod
    def test_other_users_are_pointed_to_the_commander() -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATING)
        IncidentChannelFactory.create(incident=incident)
        commander = UserFactory.create()
        commander_slack = SlackUserFactory.create(user=commander)
        _give_command(incident, commander)

        view = DowngradeWorkflowModal().build_modal_fn(
            incident=incident, user=UserFactory.create()
        )

        assert view.submit is None
        text = view.blocks[0].text.text
        assert "Only the Incident Commander" in text
        assert f"<@{commander_slack.slack_id}>" in text

    @staticmethod
    def test_commander_without_slack_account_is_named_by_role() -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATING)
        IncidentChannelFactory.create(incident=incident)
        _give_command(incident, UserFactory.create())

        view = DowngradeWorkflowModal().build_modal_fn(
            incident=incident, user=UserFactory.create()
        )

        assert view.submit is None
        assert "Please ask the Incident Commander." in view.blocks[0].text.text

    @staticmethod
    def test_links_the_jira_ticket(mocker: MockerFixture) -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATING)
        IncidentChannelFactory.create(incident=incident)
        mocker.patch.object(
            type(incident),
            "jira_ticket",
            new_callable=PropertyMock,
            return_value=MagicMock(url="https://jira.example.com/browse/INC-1"),
        )

        view = DowngradeWorkflowModal().build_modal_fn(
            incident=incident, user=UserFactory.create()
        )

        assert "<https://jira.example.com/browse/INC-1|*Jira ticket*>" in view.blocks[1].text.text

    @staticmethod
    def test_select_title_mentions_jira() -> None:
        assert "Jira incident" in DowngradeWorkflowModal().get_select_title()

    @staticmethod
    def test_closed_incident_cannot_be_switched() -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.CLOSED)

        view = DowngradeWorkflowModal().build_modal_fn(
            incident=incident, user=UserFactory.create()
        )

        assert view.submit is None
        assert "is already closed" in view.blocks[0].text.text


@pytest.mark.django_db
class TestDowngradeWorkflowModalHandle:
    @staticmethod
    def test_commander_switch_closes_with_the_workflow_event_type(
        mocker: MockerFixture,
    ) -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATING)
        commander = UserFactory.create()
        _give_command(incident, commander)
        mock_update = mocker.patch.object(incident, "create_incident_update")
        ack = MagicMock()

        DowngradeWorkflowModal.handle_modal_fn(ack=ack, user=commander, incident=incident)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.ignore is True
        mock_update.assert_called_once()
        kwargs = mock_update.call_args.kwargs
        assert kwargs["status"] == IncidentStatus.CLOSED
        assert kwargs["event_type"] == DOWNGRADE_WORKFLOW_EVENT_TYPE

    @staticmethod
    def test_other_users_cannot_switch(
        mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        incident = IncidentFactory.create(_status=IncidentStatus.MITIGATING)
        _give_command(incident, UserFactory.create())
        mock_update = mocker.patch.object(incident, "create_incident_update")

        DowngradeWorkflowModal.handle_modal_fn(
            ack=MagicMock(), user=UserFactory.create(), incident=incident
        )

        mock_update.assert_not_called()
        incident.refresh_from_db()
        assert incident.ignore is False
        assert "without being its Commander" in caplog.text
