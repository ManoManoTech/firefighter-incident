from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms
from django.conf import settings
from slack_sdk.models.blocks.blocks import SectionBlock

from firefighter.incidents.forms.create_incident import CreateIncidentForm
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.views.modals.opening.set_details import SetIncidentDetails

if TYPE_CHECKING:
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )
app = SlackApp()
logger = logging.getLogger(__name__)


class CreateIncidentFormSlack(CreateIncidentForm):
    slack_fields: SlackFormAttributesDict = {
        "title": {
            "input": {
                "multiline": False,
                "placeholder": "Short, punchy description of what's happening.",
            },
            "block": {"hint": None},
        },
        "description": {
            "input": {
                "multiline": True,
                "placeholder": "Help people responding to the incident. This will be posted to #tech-incidents and on our internal status page.\nThis description can be edited later.",
            },
            "block": {"hint": None},
        },
        "environment": {
            "input": {
                "placeholder": "Select an environment",
            },
            "widget": {
                "label_from_instance": lambda obj: f"{obj.value} - {obj.description}",
            },
        },
        "priority": {
            "input": {
                "placeholder": "Select a priority",
            },
            "widget": {
                "post_block": (
                    SectionBlock(
                        text=f"_<{settings.SLACK_SEVERITY_HELP_GUIDE_URL}|How to choose the priority?>_"
                    )
                    if settings.SLACK_SEVERITY_HELP_GUIDE_URL
                    else None
                ),
                "label_from_instance": lambda obj: f"{obj.emoji}  {obj.name} - {obj.description}",
            },
        },
        "component": {
            "input": {
                "placeholder": "Select affected issue category",
            },
        },
    }

    # Change `priority` field from parent to be a hidden field
    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["priority"].widget = forms.HiddenInput()


class OpeningCriticalModal(SetIncidentDetails[CreateIncidentFormSlack]):
    open_action: str = "open_incident_critical"
    push_action: str = "push_incident_critical"
    open_shortcut = "open_incident_critical"
    callback_id: str = "open_incident_critical"

    title = "Incident Details"
    form_class = CreateIncidentFormSlack


modal_opening_critical = OpeningCriticalModal()
