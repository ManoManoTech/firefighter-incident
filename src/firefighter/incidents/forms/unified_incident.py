from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from typing import cast as typing_cast

from django import forms
from django.db import models

from firefighter.incidents.forms.create_incident import CreateIncidentFormBase
from firefighter.incidents.forms.select_impact import SelectImpactForm
from firefighter.incidents.forms.utils import GroupedModelChoiceField
from firefighter.incidents.models import Environment, IncidentCategory, Priority
from firefighter.incidents.models.impact import LevelChoices
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import create_incident_conversation

if TYPE_CHECKING:
    from firefighter.incidents.models.impact import ImpactLevel
    from firefighter.incidents.models.user import User
    from firefighter.jira_app.models import JiraUser

logger = logging.getLogger(__name__)


class PlatformChoices(models.TextChoices):
    """Platform choices for incidents."""

    FR = "platform-FR", ":fr: FR"
    DE = "platform-DE", ":de: DE"
    IT = "platform-IT", ":it: IT"
    ES = "platform-ES", ":es: ES"
    UK = "platform-UK", ":uk: UK"
    ALL = "platform-All", ":earth_africa: ALL"
    INTERNAL = "platform-Internal", ":logo-manomano: Internal"


def initial_environments() -> list[Environment]:
    """Get default environments."""
    return list(Environment.objects.filter(default=True))


def initial_priority() -> Priority:
    """Get default priority."""
    return Priority.objects.get(default=True)


def initial_platform() -> str:
    """Get default platform."""
    return PlatformChoices.ALL.value


class UnifiedIncidentForm(CreateIncidentFormBase):
    """Unified form for all incident types and priorities (P1-P5).

    This form dynamically shows/hides fields based on:
    - Priority/response_type (critical vs normal)
    - Selected impacts (customer, seller, employee)

    Common fields (always shown):
    - title, description, incident_category
    - environment (multiple choice)
    - platform (multiple choice, default ALL)
    - priority (hidden)

    Conditional fields:
    - suggested_team_routing (P4-P5 only)
    - zendesk_ticket_id (if customer impact selected)
    - seller_contract_id, is_key_account, etc. (if seller impact selected)
    """

    # === Common fields (ALL priorities) ===
    title = forms.CharField(
        label="Title",
        max_length=128,
        min_length=10,
        widget=forms.TextInput(attrs={"placeholder": "What's going on?"}),
    )

    description = forms.CharField(
        label="Summary",
        widget=forms.Textarea(
            attrs={
                "placeholder": "Help people responding to the incident. This will be posted to #tech-incidents and on our internal status page.\nThis description can be edited later."
            }
        ),
        min_length=10,
        max_length=1200,
    )

    incident_category = GroupedModelChoiceField(
        choices_groupby="group",
        label="Incident category",
        queryset=(
            IncidentCategory.objects.all()
            .select_related("group")
            .order_by(
                "group__order",
                "name",
            )
        ),
    )

    environment = forms.ModelMultipleChoiceField(
        label="Environment",
        queryset=Environment.objects.all(),
        initial=initial_environments,
        required=True,
    )

    platform = forms.MultipleChoiceField(
        label="Platform",
        choices=PlatformChoices.choices,
        initial=[PlatformChoices.ALL.value],
        required=True,
    )

    priority = forms.ModelChoiceField(
        label="Priority",
        queryset=Priority.objects.filter(enabled_create=True),
        initial=initial_priority,
        widget=forms.HiddenInput(),
    )

    # === Conditional: Normal incidents only (P4-P5) ===
    suggested_team_routing: forms.ModelChoiceField[Any] = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        label="Feature Team or Train",
        required=False,  # Conditionally required based on response_type
    )

    # === Conditional: Customer impact ===
    zendesk_ticket_id = forms.CharField(
        label="Zendesk Ticket ID",
        max_length=128,
        min_length=2,
        required=False,
    )

    # === Conditional: Seller impact ===
    seller_contract_id = forms.CharField(
        label="Seller Contract ID",
        max_length=128,
        min_length=0,
        required=False,  # Conditionally required in clean()
    )

    is_key_account = forms.BooleanField(
        label="Is it a Key Account?",
        required=False,
    )

    is_seller_in_golden_list = forms.BooleanField(
        label="Is the seller in the Golden List?",
        required=False,
    )

    zoho_desk_ticket_id = forms.CharField(
        label="Zoho Desk Ticket ID",
        max_length=128,
        min_length=1,
        required=False,
    )

    field_order = [
        "incident_category",
        "environment",
        "platform",
        "title",
        "description",
        "suggested_team_routing",
        "zendesk_ticket_id",
        "seller_contract_id",
        "is_key_account",
        "is_seller_in_golden_list",
        "zoho_desk_ticket_id",
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize form with dynamic queryset for suggested_team_routing."""
        super().__init__(*args, **kwargs)

        # Set queryset for suggested_team_routing
        try:
            from firefighter.raid.models import FeatureTeam  # noqa: PLC0415

            field = typing_cast("forms.ModelChoiceField[Any]", self.fields["suggested_team_routing"])
            field.queryset = FeatureTeam.objects.only("name").order_by("name")
        except ImportError:
            # RAID module not available
            logger.warning("RAID module not available, suggested_team_routing will not work")

    def get_visible_fields_for_impacts(
        self, impacts_data: dict[str, ImpactLevel | str], response_type: str
    ) -> list[str]:
        """Determine which fields should be visible based on impacts and response type.

        Args:
            impacts_data: Dictionary of impact type → impact level (ImpactLevel object or UUID string)
            response_type: "critical" or "normal"

        Returns:
            List of field names that should be visible
        """
        visible_fields = [
            "title",
            "description",
            "incident_category",
            "environment",
            "platform",
            "priority",
        ]

        # Add suggested_team_routing for normal incidents (P4-P5)
        if response_type == "normal":
            visible_fields.append("suggested_team_routing")

        # Check impact selections
        customer_impact = None
        seller_impact = None

        for field_name, impact_level in impacts_data.items():
            if "customers_impact" in field_name:
                customer_impact = impact_level
            elif "sellers_impact" in field_name:
                seller_impact = impact_level

        # Helper to check if impact is not NONE
        def has_impact(impact: ImpactLevel | str | None) -> bool:
            if impact is None:
                return False

            # If it's a UUID string, fetch the ImpactLevel from database
            if isinstance(impact, str):
                from firefighter.incidents.models.impact import (  # noqa: PLC0415
                    ImpactLevel as ImpactLevelModel,
                )

                try:
                    impact_obj = ImpactLevelModel.objects.get(id=impact)
                except ImpactLevelModel.DoesNotExist:
                    return False
                else:
                    return impact_obj.value != LevelChoices.NONE.value

            # Otherwise it's an ImpactLevel object
            return impact.value != LevelChoices.NONE.value

        # Add customer-specific fields
        if has_impact(customer_impact):
            visible_fields.append("zendesk_ticket_id")

        # Add seller-specific fields
        if has_impact(seller_impact):
            visible_fields.extend([
                "seller_contract_id",
                "is_key_account",
                "is_seller_in_golden_list",
                "zoho_desk_ticket_id",
            ])

        return visible_fields

    def clean(self) -> dict[str, Any]:
        """Custom validation based on response type and impacts."""
        cleaned_data = super().clean()
        if cleaned_data is None:
            cleaned_data = {}

        # Get response_type from initial data if available
        initial = self.initial or {}
        response_type = initial.get("response_type", "critical")

        # Validate suggested_team_routing is required for normal incidents
        if response_type == "normal" and not cleaned_data.get("suggested_team_routing"):
            self.add_error(
                "suggested_team_routing",
                "Feature Team is required for P4/P5 incidents",
            )

        return cleaned_data

    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        response_type: str = "critical",
        *args: Any,
        **kwargs: Any,
    ) -> Incident:
        """Trigger unified incident workflow for all priorities.

        This unified workflow:
        1. Always creates an Incident in the database (P1-P5)
        2. Conditionally creates a Slack channel (P1-P3 only)
        3. Always creates a Jira ticket linked to the Incident (P1-P5)

        Args:
            creator: User creating the incident
            impacts_data: Dictionary of impact data
            response_type: "critical" (P1-P3) or "normal" (P4-P5)
            *args: Additional positional arguments (unused)
            **kwargs: Additional keyword arguments (unused)

        Returns:
            The created Incident object
        """
        # Step 1: Always create Incident in database (ALL priorities)
        incident = self._create_incident(creator)

        # Save impacts
        impacts_form = SelectImpactForm(impacts_data)
        impacts_form.save(incident=incident)

        # Step 2: Conditionally create Slack channel (P1-P3 only)
        if self._should_create_slack_channel(response_type):
            self._create_slack_channel(incident, impacts_data)

        # Step 3: Always create Jira ticket (ALL priorities) - UNIFIED
        self._create_jira_ticket(incident, creator, impacts_data)

        return incident

    def _should_create_slack_channel(self, response_type: str) -> bool:
        """Determine if incident needs Slack channel based on priority.

        Args:
            response_type: "critical" or "normal"

        Returns:
            True if Slack channel should be created (P1-P3), False otherwise (P4-P5)
        """
        return response_type == "critical"

    def _create_incident(self, creator: User) -> Incident:
        """Create Incident object in database for ALL priorities.

        Args:
            creator: User creating the incident

        Returns:
            Created Incident object
        """
        cleaned_data_copy = self.cleaned_data.copy()
        logger.info(f"UNIFIED FORM - cleaned_data keys: {list(self.cleaned_data.keys())}")
        logger.info(f"UNIFIED FORM - cleaned_data values: {self.cleaned_data}")

        # Extract environments and platforms (not stored directly in Incident model)
        environments = cleaned_data_copy.pop("environment", [])
        platforms = cleaned_data_copy.pop("platform", [])

        # Extract Jira-only fields (not stored in Incident model)
        # Convert suggested_team_routing to JSON-serializable value (name string)
        team_routing = cleaned_data_copy.pop("suggested_team_routing", None)
        team_routing_name = team_routing.name if team_routing else None

        self._jira_extra_fields = {
            "suggested_team_routing": team_routing_name,  # Store name string, not model instance
            "zendesk_ticket_id": cleaned_data_copy.pop("zendesk_ticket_id", None),
            "seller_contract_id": cleaned_data_copy.pop("seller_contract_id", None),
            "is_key_account": cleaned_data_copy.pop("is_key_account", None),
            "is_seller_in_golden_list": cleaned_data_copy.pop("is_seller_in_golden_list", None),
            "zoho_desk_ticket_id": cleaned_data_copy.pop("zoho_desk_ticket_id", None),
            "environments": [env.value for env in environments],
            "platforms": platforms,
        }
        logger.info(f"UNIFIED FORM - jira_extra_fields extracted: {self._jira_extra_fields}")

        # Use highest priority environment (lowest order value) for main environment field
        if environments:
            cleaned_data_copy["environment"] = min(environments, key=lambda env: env.order)

        # Store custom fields in the incident (including all environments)
        cleaned_data_copy["custom_fields"] = {
            k: v for k, v in self._jira_extra_fields.items() if v is not None
        }

        # Create Incident in database (ALL priorities)
        incident = Incident.objects.declare(created_by=creator, **cleaned_data_copy)
        logger.info(f"UNIFIED FORM - Incident created: {incident.id}")

        return incident

    def _create_slack_channel(
        self,
        incident: Incident,
        impacts_data: dict[str, ImpactLevel],
    ) -> None:
        """Create Slack channel for P1-P3 incidents only.

        Args:
            incident: The created Incident object
            impacts_data: Dictionary of impact data
        """
        logger.info(f"UNIFIED FORM - Creating Slack channel for incident {incident.id}")

        # Signal to create Slack channel (triggers bookmarks, roles message, etc.)
        create_incident_conversation.send(
            "unified_incident_form",
            incident=incident,
            jira_extra_fields=self._jira_extra_fields,
            impacts_data=impacts_data,
        )

    def _create_jira_ticket(
        self,
        incident: Incident,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
    ) -> None:
        """Create Jira ticket for ALL priorities - UNIFIED method.

        Args:
            incident: The created Incident object
            creator: User creating the incident
            impacts_data: Dictionary of impact data
        """
        from firefighter.incidents.forms.select_impact import (  # noqa: PLC0415
            SelectImpactForm,
        )
        from firefighter.raid.client import client as jira_client  # noqa: PLC0415
        from firefighter.raid.forms import (  # noqa: PLC0415
            alert_slack_new_jira_ticket,
            prepare_jira_fields,
            set_jira_ticket_watchers_raid,
        )
        from firefighter.raid.models import JiraTicket  # noqa: PLC0415
        from firefighter.raid.service import (  # noqa: PLC0415
            get_jira_user_from_user,
        )
        from firefighter.slack.messages.slack_messages import (  # noqa: PLC0415
            SlackMessageIncidentDeclaredAnnouncement,
        )

        logger.info(f"UNIFIED FORM - Creating Jira ticket for incident {incident.id}")

        # Get Jira user
        jira_user: JiraUser = get_jira_user_from_user(creator)

        # Extract environments and platforms from jira_extra_fields
        environments = self._jira_extra_fields.get("environments", [])
        platforms = self._jira_extra_fields.get("platforms", [])

        # Build description (enhanced for P1-P3 with Slack channel, simple for P4-P5)
        if hasattr(incident, "conversation"):
            # P1-P3: Enhanced description with emoji and formatting
            description = f"""{incident.description}

🧯 This incident has been created for a critical incident.
📦 Incident category: {incident.incident_category.name}
{incident.priority.emoji} Priority: {incident.priority.name}
"""
        else:
            # P4-P5: Simple description
            description = incident.description

        # Prepare all Jira fields using common function (UNIFIED for all priorities)
        jira_fields = prepare_jira_fields(
            title=incident.title,
            description=description,
            priority=incident.priority.value,
            reporter=jira_user.id,
            incident_category=incident.incident_category.name,
            environments=environments,  # All environments for all priorities
            platforms=platforms,
            impacts_data=impacts_data,
            optional_fields={
                "zendesk_ticket_id": self._jira_extra_fields.get("zendesk_ticket_id", ""),
                "seller_contract_id": self._jira_extra_fields.get("seller_contract_id", ""),
                "zoho_desk_ticket_id": self._jira_extra_fields.get("zoho_desk_ticket_id", ""),
                "is_key_account": self._jira_extra_fields.get("is_key_account"),
                "is_seller_in_golden_list": self._jira_extra_fields.get("is_seller_in_golden_list"),
                "suggested_team_routing": self._jira_extra_fields.get("suggested_team_routing"),
            },
        )

        # Create Jira issue via API (UNIFIED)
        issue_data = jira_client.create_issue(**jira_fields)
        logger.info(f"UNIFIED FORM - Jira issue created: {issue_data.get('key')}")

        # Create JiraTicket in DB, linked to Incident (UNIFIED)
        jira_ticket = JiraTicket.objects.create(**issue_data, incident=incident)

        # Save impact levels
        impacts_form = SelectImpactForm(impacts_data)
        impacts_form.save(incident=jira_ticket)

        # Set up Jira watchers
        set_jira_ticket_watchers_raid(jira_ticket)

        # Add Jira links to incident and Slack channel (if exists)
        jira_client.jira.add_simple_link(
            issue=str(jira_ticket.id),
            object={
                "url": incident.status_page_url,
                "title": f"FireFighter incident #{incident.id}",
            },
        )

        # Send Slack notifications based on priority
        # P1-P3 incidents have Slack channels, P4-P5 incidents don't
        if incident.priority.value <= 3:
            # P1-P3: Add Jira link to Slack channel (if exists)
            if hasattr(incident, "conversation"):
                logger.info(f"UNIFIED FORM - Adding Jira link to Slack channel for incident {incident.id}")
                jira_client.jira.add_simple_link(
                    issue=str(jira_ticket.id),
                    object={
                        "url": incident.conversation.link,
                        "title": f"Slack conversation #{incident.conversation.name}",
                    },
                )

                # Add Jira bookmark to channel
                incident.conversation.add_bookmark(
                    title="Jira ticket",
                    link=jira_ticket.url,
                    emoji=":jira_new:",
                )

                # Send incident announcement in channel
                incident.conversation.send_message_and_save(
                    SlackMessageIncidentDeclaredAnnouncement(incident)
                )
        else:
            # P4-P5: Send DM and raid_alert notifications
            logger.info(f"UNIFIED FORM - Sending Slack alerts for P4-P5 incident {incident.id}")
            alert_slack_new_jira_ticket(jira_ticket)

        logger.info(f"UNIFIED FORM - Jira ticket creation complete for incident {incident.id}")
