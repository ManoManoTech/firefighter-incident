from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import ActionsBlock, Block, SectionBlock
from slack_sdk.models.views import View

from firefighter.confluence.models import PostMortemManager
from firefighter.incidents.models.incident import Incident
from firefighter.slack.utils import respond
from firefighter.slack.views.modals.base_modal.base import SlackModal, app
from firefighter.slack.views.modals.base_modal.mixins import (
    IncidentSelectableModalMixin,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack


logger = logging.getLogger(__name__)


class PostMortemModal(
    IncidentSelectableModalMixin,
    SlackModal,
):
    open_action: str = "open_modal_create_postmortem"
    push_action: str = "push_modal_create_postmortem"
    callback_id: str = "incident_create_postmortem"

    def build_modal_fn(self, incident: Incident, **kwargs: Any) -> View:
        blocks: list[Block] = []

        # Check existing post-mortems
        has_confluence = _safe_has_relation(incident, "postmortem_for")
        has_jira = _safe_has_relation(incident, "jira_postmortem_for")

        if has_confluence or has_jira:
            blocks.append(
                SectionBlock(text=f"Post-mortem(s) for incident #{incident.id}:")
            )

            if has_confluence:
                blocks.append(
                    SectionBlock(
                        text=f"• Confluence: <{incident.postmortem_for.page_url}|View page>"
                    )
                )

            if has_jira:
                blocks.append(
                    SectionBlock(
                        text=f"• Jira: <{incident.jira_postmortem_for.issue_url}|{incident.jira_postmortem_for.jira_issue_key}>"
                    )
                )
        elif incident.needs_postmortem:
            blocks.append(
                SectionBlock(
                    text=f"Post-mortem for incident #{incident.id} will be automatically created when the incident reaches MITIGATED status."
                )
            )
        else:
            blocks.extend(
                [
                    SectionBlock(
                        text="P3 incident post-mortem is not mandatory. You can still have one if you think is necessary by clicking on the button below."
                    ),
                    ActionsBlock(
                        elements=[
                            ButtonElement(
                                text="Create post-mortem now",
                                action_id="incident_create_postmortem_now",
                                value=str(incident.id),
                            )
                        ]
                    ),
                ]
            )

        return View(
            type="modal",
            title="Postmortem"[:24],
            submit=None,
            callback_id=self.callback_id,
            private_metadata=str(incident.id),
            blocks=blocks,
        )

    @staticmethod
    def handle_modal_fn(ack: Ack, **_kwargs: Any) -> None:
        # This modal is now read-only (no submit button)
        # Post-mortems are created automatically when incident reaches MITIGATED status
        ack()


@app.action("incident_create_postmortem_now")
def handle_create_postmortem_action(ack: Ack, body: dict[str, Any]) -> None:
    """Create post-mortem(s) on demand from the modal (e.g. P3+ incidents)."""
    ack()

    incident_id = str(body.get("actions", [{}])[0].get("value", "")).strip()
    try:
        incident = Incident.objects.get(pk=incident_id)
    except Incident.DoesNotExist:
        respond(body, text=":x: Incident not found.")
        return

    try:
        confluence_pm, jira_pm = PostMortemManager.create_postmortem_for_incident(
            incident
        )
    except Exception:
        logger.exception("Failed to create post-mortem for incident #%s", incident_id)
        respond(body, text=":x: Failed to create post-mortem. Please try again.")
        return

    created_targets: list[str] = []
    if confluence_pm:
        created_targets.append("Confluence")
    if jira_pm:
        created_targets.append("Jira")

    if created_targets:
        targets = " and ".join(created_targets)
        respond(body, text=f":white_check_mark: {targets} post-mortem created.")
    else:
        respond(body, text=":warning: No post-mortem was created.")


modal_postmortem = PostMortemModal()


def _safe_has_relation(instance: Incident, attr: str) -> bool:
    """Safely check if a reverse relation exists without triggering KeyError in cache.

    Django's reverse OneToOne descriptor can raise KeyError when using hasattr
    on unsaved or freshly created instances. We guard against that here.
    """
    try:
        getattr(instance, attr)
    except (AttributeError, ObjectDoesNotExist, KeyError):
        return False
    else:
        return True
