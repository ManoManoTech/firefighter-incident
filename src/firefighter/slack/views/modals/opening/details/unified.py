from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms
from django.conf import settings
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.blocks import ContextBlock, SectionBlock

from firefighter.incidents.forms.unified_incident import UnifiedIncidentForm
from firefighter.slack.views.modals.base_modal.form_utils import SlackForm
from firefighter.slack.views.modals.opening.set_details import SetIncidentDetails
from firefighter.slack.views.modals.opening.types import OpeningData

if TYPE_CHECKING:
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)


class UnifiedIncidentFormSlack(UnifiedIncidentForm):
    """Slack version of UnifiedIncidentForm with Slack-specific field configurations."""

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
                "placeholder": "Select environments",
            },
        },
        "platform": {
            "input": {
                "placeholder": "Select platforms",
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
        "incident_category": {
            "input": {
                "placeholder": "Select affected issue category",
            },
        },
        "suggested_team_routing": {
            "input": {
                "placeholder": "Select feature team or train",
            },
            "widget": {
                "post_block": ContextBlock(
                    elements=[
                        MarkdownTextObject(
                            text="Feature Team or Train that should own the issue. If you don't know access <https://manomano.atlassian.net/wiki/spaces/QRAFT/pages/3970335291/Teams+and+owners|here> for guidance."
                        ),
                    ]
                )
            },
        },
        "zendesk_ticket_id": {
            "input": {
                "placeholder": "Zendesk ticket ID (if applicable)",
            },
            "block": {
                "hint": "Link this incident to an existing Zendesk customer ticket"
            },
        },
        "seller_contract_id": {
            "input": {
                "placeholder": "Seller contract ID",
            },
        },
        "zoho_desk_ticket_id": {
            "input": {
                "placeholder": "Zoho Desk ticket ID (if applicable)",
            },
            "block": {
                "hint": "Link this incident to an existing Zoho Desk seller ticket"
            },
        },
    }

    def __init__(
        self,
        *args: Any,
        impacts_data: dict[str, Any] | None = None,
        response_type: str = "critical",
        **kwargs: Any,
    ) -> None:
        """Initialize form with impact-based field visibility.

        Args:
            *args: Positional arguments passed to parent form
            impacts_data: Dictionary of impact selections
            response_type: "critical" or "normal"
            **kwargs: Keyword arguments passed to parent form
        """
        super().__init__(*args, **kwargs)

        # Store for later use
        self._impacts_data = impacts_data or {}
        self._response_type = response_type

        # Make priority field hidden
        self.fields["priority"].widget = forms.HiddenInput()

        # Conditionally hide fields based on impacts and response_type
        self._configure_field_visibility()

    def _configure_field_visibility(self) -> None:
        """Configure which fields should be visible based on impacts and response type."""
        visible_fields = self.get_visible_fields_for_impacts(
            self._impacts_data, self._response_type
        )

        # Remove fields that shouldn't be visible
        fields_to_remove = [
            field_name for field_name in self.fields if field_name not in visible_fields
        ]

        for field_name in fields_to_remove:
            del self.fields[field_name]


class OpeningUnifiedModal(SetIncidentDetails[UnifiedIncidentFormSlack]):
    """Unified modal for all incident types (P1-P5)."""

    open_action: str = "open_incident_unified"
    push_action: str = "push_incident_unified"
    callback_id: str = "open_incident_unified"
    id = "incident_unified"

    title = "Incident Details"
    form_class = UnifiedIncidentFormSlack

    def get_form_class(self) -> Any:
        """Return a SlackForm wrapper that passes impacts_data and response_type."""
        form_class = self.form_class

        # Create a custom form class that accepts our parameters
        class ContextAwareForm(form_class):  # type: ignore
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                # Extract context from kwargs
                open_incident_context = kwargs.pop("open_incident_context", None)
                if open_incident_context:
                    kwargs["impacts_data"] = open_incident_context.get("impact_form_data", {})
                    kwargs["response_type"] = open_incident_context.get("response_type", "critical")
                super().__init__(*args, **kwargs)

        # Return SlackForm wrapping the context-aware form
        return SlackForm(ContextAwareForm)

    def build_modal_fn(
        self, open_incident_context: OpeningData | None = None, **kwargs: Any
    ) -> Any:
        """Build modal with impact-aware form."""
        # Extract impacts and response type from context
        if open_incident_context is None:
            open_incident_context = OpeningData()

        response_type = open_incident_context.get("response_type", "critical")

        # Store in initial data so form can access it
        details_form_data = open_incident_context.get("details_form_data")
        if details_form_data is None:
            details_form_data = {}
        details_form_data["response_type"] = response_type

        # Update context
        open_incident_context["details_form_data"] = details_form_data

        # Store context for get_form_class in kwargs
        # Call parent build_modal_fn with open_incident_context in kwargs
        return super().build_modal_fn(open_incident_context=open_incident_context, **kwargs)


modal_opening_unified = OpeningUnifiedModal()
