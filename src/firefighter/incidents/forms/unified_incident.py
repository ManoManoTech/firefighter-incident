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
    ) -> None:
        """Trigger the appropriate incident workflow based on response type.

        Args:
            creator: User creating the incident
            impacts_data: Dictionary of impact data
            response_type: "critical" or "normal"
            *args: Additional positional arguments (unused)
            **kwargs: Additional keyword arguments (unused)
        """
        if response_type == "critical":
            self._trigger_critical_incident_workflow(creator, impacts_data)
        else:
            self._trigger_normal_incident_workflow(creator, impacts_data)

    def _trigger_critical_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
    ) -> None:
        """Create a critical incident (P1-P3) with Slack channel."""
        # Create incident with first environment only (critical incidents use single env)
        cleaned_data_copy = self.cleaned_data.copy()
        logger.info(f"UNIFIED FORM - cleaned_data keys: {list(self.cleaned_data.keys())}")
        logger.info(f"UNIFIED FORM - cleaned_data values: {self.cleaned_data}")

        environments = cleaned_data_copy.pop("environment", [])
        platforms = cleaned_data_copy.pop("platform", [])

        # Extract customer/seller fields for Jira ticket (not stored in Incident model)
        jira_extra_fields = {
            "suggested_team_routing": cleaned_data_copy.pop("suggested_team_routing", None),
            "zendesk_ticket_id": cleaned_data_copy.pop("zendesk_ticket_id", None),
            "seller_contract_id": cleaned_data_copy.pop("seller_contract_id", None),
            "is_key_account": cleaned_data_copy.pop("is_key_account", None),
            "is_seller_in_golden_list": cleaned_data_copy.pop("is_seller_in_golden_list", None),
            "zoho_desk_ticket_id": cleaned_data_copy.pop("zoho_desk_ticket_id", None),
            # Pass full lists for Jira ticket creation
            "environments": [env.value for env in environments],  # Convert QuerySet to list of values
            "platforms": platforms,  # Already a list of strings
        }
        logger.info(f"UNIFIED FORM - jira_extra_fields extracted: {jira_extra_fields}")

        # Use first environment
        if environments:
            cleaned_data_copy["environment"] = environments[0]

        # Store custom fields in the incident
        cleaned_data_copy["custom_fields"] = {
            k: v for k, v in jira_extra_fields.items() if v is not None
        }

        incident = Incident.objects.declare(created_by=creator, **cleaned_data_copy)
        impacts_form = SelectImpactForm(impacts_data)
        impacts_form.save(incident=incident)

        create_incident_conversation.send(
            "unified_incident_form",
            incident=incident,
            jira_extra_fields=jira_extra_fields,
            impacts_data=impacts_data,  # Pass impacts_data for business_impact computation
        )

    def _trigger_normal_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
    ) -> None:
        """Create a normal incident (P4-P5) with Jira ticket only."""
        from firefighter.raid.client import client as jira_client  # noqa: PLC0415
        from firefighter.raid.forms import (  # noqa: PLC0415
            prepare_jira_fields,
            process_jira_issue,
        )
        from firefighter.raid.service import (  # noqa: PLC0415
            get_jira_user_from_user,
        )

        jira_user: JiraUser = get_jira_user_from_user(creator)

        # Extract environments and platforms
        environments_qs = self.cleaned_data.get("environment", [])
        environments = [env.value for env in environments_qs]  # Convert QuerySet to list of values
        platforms = self.cleaned_data.get("platform", [])

        # Extract suggested team routing (convert FeatureTeam instance to string)
        team_routing = self.cleaned_data.get("suggested_team_routing")
        team_routing_name = team_routing.name if team_routing else None

        # Prepare all Jira fields using the common function
        # P4-P5 pass all environments (unlike P1-P3 which pass first only)
        jira_fields = prepare_jira_fields(
            title=self.cleaned_data["title"],
            description=self.cleaned_data["description"],
            priority=self.cleaned_data["priority"].value,
            reporter=jira_user.id,
            incident_category=self.cleaned_data["incident_category"].name,
            environments=environments,  # ✅ P4-P5: pass ALL environments
            platforms=platforms,
            impacts_data=impacts_data,
            optional_fields={
                "zendesk_ticket_id": self.cleaned_data.get("zendesk_ticket_id", ""),
                "seller_contract_id": self.cleaned_data.get("seller_contract_id", ""),
                "zoho_desk_ticket_id": self.cleaned_data.get("zoho_desk_ticket_id", ""),
                "is_key_account": self.cleaned_data.get("is_key_account"),
                "is_seller_in_golden_list": self.cleaned_data.get("is_seller_in_golden_list"),
                "suggested_team_routing": team_routing_name,
            },
        )

        # Create Jira issue with all prepared fields
        issue_data = jira_client.create_issue(**jira_fields)

        # Process the created Jira ticket (create JiraTicket in DB, save impacts, alert Slack)
        process_jira_issue(
            issue_data, creator, jira_user=jira_user, impacts_data=impacts_data
        )
