from __future__ import annotations

import datetime
import logging
import re
from typing import TYPE_CHECKING, Any, cast

from django.core.cache import cache as dj_cache
from django.utils import timezone
from slack_sdk.models.blocks import Block, ContextBlock, HeaderBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from firefighter.incidents.forms.update_key_events import IncidentUpdateKeyEventsForm
from firefighter.slack.messages.base import SlackMessageStrategy, SlackMessageSurface
from firefighter.slack.views.modals.base_modal.base import MessageForm

if TYPE_CHECKING:
    from django_redis.client.default import DefaultClient
    from slack_bolt.context.ack.ack import Ack

    from firefighter.incidents.models.incident import Incident, User
    from firefighter.slack.views.modals.base_modal.form_utils import SlackForm

cache = cast("DefaultClient", dj_cache)
logger = logging.getLogger(__name__)

# XXX Remove legacy `post_mortem_milestone` once we're sure it's not used anymore
MILESTONE_ID_REGEX = re.compile(
    r"^(post_mortem_milestone|key_event)_?(?P<type>date|time|clear)?_(?P<id>.*)$"
)

TZ = timezone.get_current_timezone()


class KeyEvents(MessageForm[IncidentUpdateKeyEventsForm]):
    form_class = IncidentUpdateKeyEventsForm
    callback_id = MILESTONE_ID_REGEX
    callback_action = True
    wrapper = "action"

    def build_modal_fn(self, incident: Incident) -> list[Block]:
        slack_form: SlackForm[IncidentUpdateKeyEventsForm] = self.get_form_class()(
            incident=incident
        )

        return self.get_blocks_from_form(slack_form.form)

    def get_blocks_from_form(self, form: IncidentUpdateKeyEventsForm) -> list[Block]:
        blocks: list[Block] = [HeaderBlock(text=":stopwatch:  Key events time")]
        slack_form: SlackForm[IncidentUpdateKeyEventsForm] = self.get_form_class()
        slack_form.form = form
        blocks += slack_form.slack_blocks()
        # XXX Check form.is_valid()
        missing_milestones = form.incident.missing_milestones()
        if len(missing_milestones) > 0:
            blocks.append(
                SectionBlock(
                    text=f":warning: Some required key events are missing: {', '.join(missing_milestones)}. Once all required key events have been submitted, you'll be able to to close this incident."
                )
            )
        else:
            blocks.append(
                # XXX Check if postmortem and change message
                SectionBlock(
                    text=":white_check_mark: All required key events have been submitted. Once you're ready, you can close the incident.",
                    accessory=ButtonElement(
                        text="Close incident",
                        value=str(form.incident.id),
                        action_id="close_incident",
                    ),
                )
            )
        blocks.append(
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=f"Last update: {datetime.datetime.now(tz=timezone.get_current_timezone()).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                ]
            ),
        )
        return blocks

    def handle_modal_fn(  # type: ignore[override]
        self, ack: Ack, body: dict[str, Any], user: User, incident: Incident
    ) -> None:
        """Handle the time and date inputs for the key events."""
        logger.debug(body)

        slack_form: SlackForm[IncidentUpdateKeyEventsForm] | None = (
            self.handle_form_errors(
                ack,
                body,
                forms_kwargs={
                    "incident": incident,
                    "user": user,
                },
            )
        )
        form = slack_form.form if slack_form else None

        if form is None:
            logger.warning("Form is None, skipping save")
            return
        if len(form.errors) > 0:
            self.update_with_form()
            return
        self.form = form
        self.form.save()
        incident.compute_metrics()

        self.update_with_form()

    def update_with_form(
        self,
    ) -> None:
        self.form.incident.conversation.send_message_and_save(
            SlackMessageKeyEvents(self.form.incident)
        )


key_events_surface = KeyEvents()


class SlackMessageKeyEvents(SlackMessageSurface):
    id = "ff_incident_key_events_form"
    strategy: SlackMessageStrategy = SlackMessageStrategy.UPDATE
    incident: Incident | None
    form: IncidentUpdateKeyEventsForm | None

    def __init__(
        self,
        incident: Incident | None = None,
        form: IncidentUpdateKeyEventsForm | None = None,
    ) -> None:
        if incident is None and form is None:
            raise ValueError("Either incident or form must be set")
        self.incident = incident
        self.form = form
        super().__init__()

    def get_blocks(self) -> list[Block]:
        if self.incident is not None:
            return KeyEvents().build_modal_fn(self.incident)
        if self.form is not None:
            return KeyEvents().get_blocks_from_form(self.form)

        raise ValueError("Either incident or form must be set")

    def get_text(self) -> str:
        if self.incident:
            incident = self.incident
        elif self.form:
            incident = self.form.incident
        else:
            raise ValueError("Either incident or form must be set")
        return f"Please fill the Key events for {incident}."
