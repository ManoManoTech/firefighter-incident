from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.forms.select_impact import SelectImpactForm
from firefighter.incidents.forms.utils import GroupedModelChoiceField
from firefighter.incidents.models import Environment, IncidentCategory, Priority
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.signals import create_incident_conversation

if TYPE_CHECKING:
    from firefighter.incidents.models.impact import ImpactLevel
    from firefighter.incidents.models.user import User


def initial_environments() -> Environment:
    return Environment.objects.get(default=True)


def initial_priority() -> Priority:
    return Priority.objects.get(default=True)


class CreateIncidentFormBase(forms.Form):
    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError


class CreateIncidentForm(CreateIncidentFormBase):
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
    priority = forms.ModelChoiceField(
        label="Priority",
        queryset=Priority.objects.filter(enabled_create=True),
        initial=initial_priority,
    )
    environment = forms.ModelChoiceField(
        label="Environment",
        queryset=Environment.objects.all(),
        initial=initial_environments,
    )

    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Any,
        **kwargs: Any,
    ) -> Incident:
        """Create Incident and JiraTicket following unified workflow.

        This method follows the unified workflow:
        1. Create Incident in database
        2. Create Slack conversation (for P1-P3)
        3. Create Jira ticket via API
        4. Link JiraTicket to Incident
        """
        import logging  # noqa: PLC0415

        from firefighter.raid.client import client as jira_client  # noqa: PLC0415
        from firefighter.raid.forms import prepare_jira_fields  # noqa: PLC0415
        from firefighter.raid.models import JiraTicket  # noqa: PLC0415
        from firefighter.raid.service import get_jira_user_from_user  # noqa: PLC0415

        logger = logging.getLogger(__name__)

        # Step 1: Create Incident in database
        incident = Incident.objects.declare(created_by=creator, **self.cleaned_data)
        impacts_form = SelectImpactForm(impacts_data)
        impacts_form.save(incident=incident)

        # Step 2: Create Slack conversation (if P1-P3)
        create_incident_conversation.send(
            "create_incident_form",
            incident=incident,
        )
        logger.info(f"WEB FORM - Incident created: {incident.id}")

        # Step 3 & 4: Create and link JiraTicket (unified workflow)
        try:
            jira_user = get_jira_user_from_user(creator)

            # Prepare Jira fields
            jira_fields = prepare_jira_fields(
                title=incident.title,
                description=incident.description,
                priority=incident.priority.value,
                reporter=jira_user.id,
                incident_category=incident.incident_category.name,
                environments=[incident.environment.value] if incident.environment else [],
                platforms=[],
                impacts_data=impacts_data,
                optional_fields={},
            )

            # Create Jira issue
            issue_data = jira_client.create_issue(**jira_fields)
            logger.info(f"WEB FORM - Jira issue created: {issue_data.get('key')}")

            # Create JiraTicket linked to Incident
            jira_ticket = JiraTicket.objects.create(**issue_data, incident=incident)
            logger.info(f"WEB FORM - JiraTicket {jira_ticket.key} linked to Incident {incident.id}")

            # Add link from Jira to FireFighter
            jira_client.jira.add_simple_link(
                issue=str(jira_ticket.id),
                object={
                    "url": incident.status_page_url,
                    "title": f"FireFighter incident #{incident.id}",
                },
            )

            # For P1-P3 with Slack channels, add Jira link to channel
            if hasattr(incident, "conversation"):
                jira_client.jira.add_simple_link(
                    issue=str(jira_ticket.id),
                    object={
                        "url": incident.conversation.link,
                        "title": f"Slack conversation #{incident.conversation.name}",
                    },
                )
                incident.conversation.add_bookmark(
                    title="Jira ticket",
                    link=jira_ticket.url,
                    emoji=":jira_new:",
                )
        except Exception:
            logger.exception(f"WEB FORM - Failed to create JiraTicket for Incident {incident.id}")
            # Don't fail the incident creation if Jira fails

        return incident
