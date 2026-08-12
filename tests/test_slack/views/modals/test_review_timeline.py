from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import ActionsBlock, HeaderBlock, SectionBlock

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.factories import IncidentFactory, UserFactory
from firefighter.incidents.models.incident_update import IncidentUpdate
from firefighter.slack.factories import IncidentChannelFactory, SlackUserFactory
from firefighter.slack.messages.base import SlackMessageStrategy
from firefighter.slack.views.modals.review_timeline import (
    ACCEPT_ACTION_ID,
    REJECT_ACTION_ID,
    SlackMessageReviewTimeline,
    SlackMessageTimelineCorrection,
    TimelineCorrection,
    TimelineEntry,
    _resolved_message_strategy_args,
    build_carry_over_payload,
    get_incident_timeline,
    get_status_timeline,
    handle_review_timeline_accept,
    handle_review_timeline_reject,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from firefighter.incidents.models.incident import Incident


@pytest.mark.django_db
class TestGetStatusTimeline:
    @staticmethod
    def test_open_anchors_to_created_at_even_if_declaration_row_differs() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user = UserFactory.create()

        # The declaration's own OPEN row, at the same instant as created_at -
        # this is the row the anchor represents, so it must not double up.
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=incident.created_at,
            created_by=user,
        )

        timeline = get_status_timeline(incident)
        assert timeline == [(IncidentStatus.OPEN, incident.created_at)]

    @staticmethod
    def test_reopen_to_open_shows_as_its_own_later_entry() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user = UserFactory.create()
        reopened_at = incident.created_at + timezone.timedelta(days=1)

        # A genuine reopen back to OPEN, distinct from the declaration.
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=reopened_at,
            created_by=user,
        )

        timeline = get_status_timeline(incident)

        assert timeline == [
            (IncidentStatus.OPEN, incident.created_at),
            (IncidentStatus.OPEN, reopened_at),
        ]

    @staticmethod
    def test_reopen_loop_includes_every_occurrence_chronologically() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        base_time = timezone.now()

        # First pass: INVESTIGATING -> MITIGATING -> MITIGATED
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=10),
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=base_time + timezone.timedelta(minutes=20),
            created_by=user,
        )
        # Reopen: back to INVESTIGATING, then MITIGATING, then MITIGATED again.
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.INVESTIGATING,
            event_ts=base_time + timezone.timedelta(minutes=30),
            created_by=user,
            message="Reopening: found a regression.",
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATING,
            event_ts=base_time + timezone.timedelta(minutes=40),
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=base_time + timezone.timedelta(minutes=50),
            created_by=user,
        )

        timeline = get_status_timeline(incident)
        statuses = [status for status, _ in timeline]

        # Every occurrence is kept, in chronological order - including the
        # full reopen cycle, matching the Jira post-mortem timeline.
        assert statuses == [
            IncidentStatus.OPEN,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
            IncidentStatus.MITIGATED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.MITIGATING,
            IncidentStatus.MITIGATED,
        ]

        event_timestamps = [event_ts for _, event_ts in timeline]
        assert event_timestamps == [
            incident.created_at,
            base_time,
            base_time + timezone.timedelta(minutes=10),
            base_time + timezone.timedelta(minutes=20),
            base_time + timezone.timedelta(minutes=30),
            base_time + timezone.timedelta(minutes=40),
            base_time + timezone.timedelta(minutes=50),
        ]


@pytest.mark.django_db
class TestGetIncidentTimeline:
    @staticmethod
    def test_includes_recorded_milestones_before_status_timeline() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        started_at = incident.created_at - timezone.timedelta(hours=2)
        detected_at = incident.created_at - timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=started_at,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=detected_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Started", event_ts=started_at)
        assert timeline[1] == TimelineEntry(label="Detected", event_ts=detected_at)
        assert timeline[2].label == "Declared"
        assert timeline[2].event_ts == incident.created_at

    @staticmethod
    def test_missing_milestones_show_as_not_recorded() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Started", event_ts=None)
        assert timeline[1] == TimelineEntry(label="Detected", event_ts=None)

    @staticmethod
    def test_milestones_sort_chronologically_among_themselves() -> None:
        """Detected can legitimately be recorded before Started (e.g. an
        automated alert fires before the actual start is pinpointed) - the
        milestone group must reflect that, not the fixed Started-then-Detected
        declaration order.
        """
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        detected_at = incident.created_at - timezone.timedelta(hours=2)
        started_at = incident.created_at - timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="started",
            event_ts=started_at,
            created_by=user,
        )
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=detected_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Detected", event_ts=detected_at)
        assert timeline[1] == TimelineEntry(label="Started", event_ts=started_at)

    @staticmethod
    def test_unrecorded_milestone_sorts_after_a_recorded_one() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        detected_at = incident.created_at - timezone.timedelta(hours=1)
        IncidentUpdate.objects.create(
            incident=incident,
            event_type="detected",
            event_ts=detected_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)

        assert timeline[0] == TimelineEntry(label="Detected", event_ts=detected_at)
        assert timeline[1] == TimelineEntry(label="Started", event_ts=None)

    @staticmethod
    def test_only_the_first_open_is_labeled_declared() -> None:
        """A later reopen to OPEN is a real status, not the declaration - it
        must keep reading "Open", not "Declared" a second time.
        """
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.OPEN)
        user = UserFactory.create()
        reopened_at = incident.created_at + timezone.timedelta(days=1)
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.OPEN,
            event_ts=reopened_at,
            created_by=user,
        )

        timeline = get_incident_timeline(incident)
        status_entries = timeline[2:]

        assert status_entries == [
            TimelineEntry(label="Declared", event_ts=incident.created_at),
            TimelineEntry(label="Open", event_ts=reopened_at),
        ]


@pytest.mark.django_db
class TestBuildCarryOverPayload:
    @staticmethod
    def test_roundtrip_excludes_status_and_stringifies_ids() -> None:
        incident: Incident = IncidentFactory.build(id=42)
        update_kwargs = {
            "status": IncidentStatus.POST_MORTEM,
            "priority_id": "e12c3836-ea9b-44bf-a3cf-5a715d62395b",
            "message": "All good.",
        }

        payload = json.loads(build_carry_over_payload(incident, update_kwargs))

        assert payload["incident_id"] == 42
        assert payload["priority_id"] == "e12c3836-ea9b-44bf-a3cf-5a715d62395b"
        assert payload["message"] == "All good."
        assert "status" not in payload


@pytest.mark.django_db
class TestSlackMessageReviewTimelineBlocks:
    @staticmethod
    def test_pending_shows_accept_and_reject_buttons() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = SlackMessageReviewTimeline(
            incident, carry_over_payload='{"incident_id": 1}'
        ).get_blocks()

        actions_blocks = [b for b in blocks if isinstance(b, ActionsBlock)]
        assert len(actions_blocks) == 1
        buttons = actions_blocks[0].elements
        assert all(isinstance(b, ButtonElement) for b in buttons)
        action_ids = {b.action_id for b in buttons}
        assert action_ids == {ACCEPT_ACTION_ID, REJECT_ACTION_ID}

    @staticmethod
    def test_shows_a_stopwatch_header() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = SlackMessageReviewTimeline(
            incident, carry_over_payload='{"incident_id": 1}'
        ).get_blocks()

        headers = [b for b in blocks if isinstance(b, HeaderBlock)]
        assert len(headers) == 1
        assert headers[0].text.text == ":stopwatch: Timeline Review"

    @staticmethod
    def test_pending_shows_not_recorded_for_missing_milestones() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = SlackMessageReviewTimeline(
            incident, carry_over_payload='{"incident_id": 1}'
        ).get_blocks()

        section_texts = [
            b.text.text for b in blocks if isinstance(b, SectionBlock)
        ]
        assert any("*Started*: _Not recorded_" in text for text in section_texts)
        assert any("*Detected*: _Not recorded_" in text for text in section_texts)

    @staticmethod
    def test_accepted_shows_confirmation_and_no_buttons() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.POST_MORTEM)

        blocks = SlackMessageReviewTimeline(incident, resolution="accepted").get_blocks()

        assert not any(isinstance(b, ActionsBlock) for b in blocks)
        section_texts = [
            b.text.text for b in blocks if isinstance(b, SectionBlock)
        ]
        assert any(
            "Timeline accepted" in text and "Post-mortem" in text
            for text in section_texts
        )

    @staticmethod
    def test_accepted_shows_the_recorded_post_mortem_time() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        user = UserFactory.create()
        post_mortem_at = timezone.now()
        IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.POST_MORTEM,
            event_ts=post_mortem_at,
            created_by=user,
        )

        blocks = SlackMessageReviewTimeline(incident, resolution="accepted").get_blocks()

        section_texts = [
            b.text.text for b in blocks if isinstance(b, SectionBlock)
        ]
        assert any(
            text.startswith(f"• *{IncidentStatus.POST_MORTEM.label}*:")
            and "_Not recorded_" not in text
            for text in section_texts
        )

    @staticmethod
    def test_rejected_shows_the_rejection_notice_and_no_buttons() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = SlackMessageReviewTimeline(incident, resolution="rejected").get_blocks()

        assert not any(isinstance(b, ActionsBlock) for b in blocks)
        section_texts = [
            b.text.text for b in blocks if isinstance(b, SectionBlock)
        ]
        assert any(
            "Timeline not accepted" in text
            and "Post-mortem transition was cancelled" in text
            for text in section_texts
        )


@pytest.mark.django_db
class TestReviewTimelineActions:
    @staticmethod
    def test_accept_creates_post_mortem_update_and_updates_message(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        user = UserFactory.create()
        slack_user = SlackUserFactory.create(user=user)

        send_and_save = mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )

        payload = json.dumps({"incident_id": incident.id, "message": "Wrapped up."})
        body = {
            "user": {"id": slack_user.slack_id},
            "actions": [{"value": payload}],
        }
        ack = MagicMock()

        handle_review_timeline_accept(ack=ack, body=body)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.POST_MORTEM
        # The POST_MORTEM transition itself fires the pre-existing "next
        # actions" message via other signal handlers; we only care that our
        # own review-timeline confirmation message was among the calls.
        review_calls = [
            call
            for call in send_and_save.call_args_list
            if isinstance(call.args[0], SlackMessageReviewTimeline)
        ]
        assert len(review_calls) == 1
        assert review_calls[0].args[0].resolution == "accepted"

    @staticmethod
    def test_accept_pushes_confirmed_timeline_to_jira_when_installed(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        slack_user = SlackUserFactory.create()
        mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )
        mocker.patch("django.apps.apps.is_installed", return_value=True)
        sync_timeline = mocker.patch(
            "firefighter.jira_app.signals.sync_timeline_to_jira_postmortem"
        )

        payload = json.dumps({"incident_id": incident.id})
        body = {"user": {"id": slack_user.slack_id}, "actions": [{"value": payload}]}

        handle_review_timeline_accept(ack=MagicMock(), body=body)

        sync_timeline.assert_called_once_with(incident)

    @staticmethod
    def test_accept_skips_jira_push_when_app_not_installed(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        slack_user = SlackUserFactory.create()
        mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )
        mocker.patch("django.apps.apps.is_installed", return_value=False)
        sync_timeline = mocker.patch(
            "firefighter.jira_app.signals.sync_timeline_to_jira_postmortem"
        )

        payload = json.dumps({"incident_id": incident.id})
        body = {"user": {"id": slack_user.slack_id}, "actions": [{"value": payload}]}

        handle_review_timeline_accept(ack=MagicMock(), body=body)

        sync_timeline.assert_not_called()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.POST_MORTEM

    @staticmethod
    def test_reject_does_not_change_status_and_updates_message(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)

        send_and_save = mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )

        payload = json.dumps({"incident_id": incident.id})
        body = {"actions": [{"value": payload}]}
        ack = MagicMock()

        handle_review_timeline_reject(ack=ack, body=body)

        ack.assert_called_once_with()
        incident.refresh_from_db()
        assert incident.status == IncidentStatus.MITIGATED

        # Posts the rejection notice, and the correction message (not just a
        # pointer to a separate form) so the human can immediately correct
        # times.
        assert send_and_save.call_count == 2
        rejection_call, correction_call = send_and_save.call_args_list
        assert rejection_call.args[0].resolution == "rejected"
        assert isinstance(correction_call.args[0], SlackMessageTimelineCorrection)
        # REPLACE, not the class default UPDATE: a new reject cycle should
        # remove a stale correction message from a previous cycle rather
        # than editing it in place.
        assert correction_call.kwargs["strategy"] == SlackMessageStrategy.REPLACE

    @staticmethod
    def test_accept_targets_the_clicked_message_explicitly(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        slack_user = SlackUserFactory.create()
        send_and_save = mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )

        payload = json.dumps({"incident_id": incident.id})
        body = {
            "user": {"id": slack_user.slack_id},
            "actions": [{"value": payload}],
            "channel": {"id": "C0123456"},
            "container": {"type": "message", "message_ts": "1690000000.123456"},
        }

        handle_review_timeline_accept(ack=MagicMock(), body=body)

        review_call = next(
            call
            for call in send_and_save.call_args_list
            if isinstance(call.args[0], SlackMessageReviewTimeline)
        )
        assert review_call.kwargs["strategy"] == SlackMessageStrategy.UPDATE
        assert review_call.kwargs["strategy_args"] == {
            "ts": "1690000000.123456",
            "channel_id": "C0123456",
        }

    @staticmethod
    def test_reject_targets_the_clicked_message_explicitly(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        send_and_save = mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )

        payload = json.dumps({"incident_id": incident.id})
        body = {
            "actions": [{"value": payload}],
            "channel": {"id": "C0123456"},
            "container": {"type": "message", "message_ts": "1690000000.654321"},
        }

        handle_review_timeline_reject(ack=MagicMock(), body=body)

        rejection_call = send_and_save.call_args_list[0]
        assert rejection_call.kwargs["strategy"] == SlackMessageStrategy.UPDATE
        assert rejection_call.kwargs["strategy_args"] == {
            "ts": "1690000000.654321",
            "channel_id": "C0123456",
        }


@pytest.mark.django_db
class TestTimelineCorrection:
    @staticmethod
    def test_build_modal_fn_returns_the_form_blocks() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = TimelineCorrection().build_modal_fn(incident=incident)

        assert len(blocks) > 0

    @staticmethod
    def test_shows_a_stopwatch_header() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = TimelineCorrection().build_modal_fn(incident=incident)

        headers = [b for b in blocks if isinstance(b, HeaderBlock)]
        assert len(headers) == 1
        assert headers[0].text.text == ":stopwatch: Correct the timeline"

    @staticmethod
    def test_shows_a_continue_to_post_mortem_button() -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)

        blocks = TimelineCorrection().build_modal_fn(incident=incident)

        actions_blocks = [b for b in blocks if isinstance(b, ActionsBlock)]
        assert len(actions_blocks) == 1
        buttons = actions_blocks[0].elements
        assert len(buttons) == 1
        assert buttons[0].action_id == ACCEPT_ACTION_ID
        payload = json.loads(buttons[0].value)
        assert payload == {"incident_id": incident.id}

    @staticmethod
    def test_continue_button_triggers_the_post_mortem_transition(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        slack_user = SlackUserFactory.create()
        mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )

        blocks = TimelineCorrection().build_modal_fn(incident=incident)
        actions_blocks = [b for b in blocks if isinstance(b, ActionsBlock)]
        continue_button = actions_blocks[0].elements[0]
        body = {
            "user": {"id": slack_user.slack_id},
            "actions": [{"value": continue_button.value}],
        }

        handle_review_timeline_accept(ack=MagicMock(), body=body)

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.POST_MORTEM

    @staticmethod
    def test_handle_modal_fn_saves_corrections_and_reposts_the_correction_message(
        mocker: MockerFixture,
    ) -> None:
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        user = UserFactory.create()
        update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=timezone.now(),
            created_by=user,
        )
        corrected_time = update.event_ts - timezone.timedelta(hours=2)
        send_and_save = mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )
        compute_metrics = mocker.patch.object(incident, "compute_metrics")

        field_name = f"status_{update.id}"
        body = {
            "type": "block_actions",
            "state": {
                "values": {
                    field_name: {
                        field_name: {
                            "type": "datetimepicker",
                            "selected_date_time": int(corrected_time.timestamp()),
                        }
                    }
                }
            },
        }

        TimelineCorrection().handle_modal_fn(
            ack=MagicMock(), body=body, user=user, incident=incident
        )

        update.refresh_from_db()
        assert update.event_ts == datetime.datetime.fromtimestamp(
            int(corrected_time.timestamp()), tz=timezone.get_current_timezone()
        )
        compute_metrics.assert_called_once()

        # Editing a single field must only refresh the correction message
        # itself - reposting the "rejected" review message here too would
        # move/repost it in the channel on every single field edit.
        assert not any(
            isinstance(call.args[0], SlackMessageReviewTimeline)
            for call in send_and_save.call_args_list
        )
        correction_call = next(
            call
            for call in send_and_save.call_args_list
            if isinstance(call.args[0], SlackMessageTimelineCorrection)
        )
        # Uses the class default (UPDATE) - no reason to delete/repost on
        # every field change, unlike starting a brand new reject cycle (see
        # handle_review_timeline_reject).
        assert "strategy" not in correction_call.kwargs

    @staticmethod
    def test_handle_modal_fn_surfaces_the_validation_error_and_does_not_crash(
        mocker: MockerFixture,
    ) -> None:
        """Clearing a required `status_*` field must not silently revert with
        no explanation, and `update_with_form()` must not crash on a
        `self.form` that was never assigned - e.g. a cold instance whose
        first-ever handled edit happens to be invalid.
        """
        incident: Incident = IncidentFactory.create(_status=IncidentStatus.MITIGATED)
        IncidentChannelFactory.create(incident=incident)
        user = UserFactory.create()
        update = IncidentUpdate.objects.create(
            incident=incident,
            _status=IncidentStatus.MITIGATED,
            event_ts=incident.created_at + timezone.timedelta(hours=1),
            created_by=user,
        )
        send_and_save = mocker.patch(
            "firefighter.slack.models.conversation.Conversation.send_message_and_save"
        )

        field_name = f"status_{update.id}"
        body = {
            "type": "block_actions",
            "state": {
                "values": {
                    field_name: {
                        field_name: {
                            "type": "datetimepicker",
                            # No "selected_date_time" - the user cleared a
                            # required field.
                        }
                    }
                }
            },
        }
        ack = MagicMock()

        TimelineCorrection().handle_modal_fn(
            ack=ack, body=body, user=user, incident=incident
        )

        update.refresh_from_db()
        assert update.event_ts == incident.created_at + timezone.timedelta(hours=1)

        ack.assert_called_once()
        assert "required" in ack.call_args.kwargs["text"].lower()

        # The message still refreshes - no crash from an unset `self.form`.
        assert any(
            isinstance(call.args[0], SlackMessageTimelineCorrection)
            for call in send_and_save.call_args_list
        )


class TestResolvedMessageStrategyArgs:
    @staticmethod
    def test_extracts_ts_and_channel_from_a_real_interaction_payload() -> None:
        body = {
            "channel": {"id": "C0123456"},
            "container": {"type": "message", "message_ts": "1690000000.123456"},
        }

        assert _resolved_message_strategy_args(body) == {
            "ts": "1690000000.123456",
            "channel_id": "C0123456",
        }

    @staticmethod
    def test_returns_none_when_fields_are_missing() -> None:
        assert _resolved_message_strategy_args({"actions": []}) is None
