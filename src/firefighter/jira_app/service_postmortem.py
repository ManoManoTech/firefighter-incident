"""Service for creating and managing Jira post-mortems."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.template.loader import render_to_string

from firefighter.jira_app.client import JiraClient
from firefighter.jira_app.models import JiraPostMortem

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


class JiraPostMortemService:
    """Service for creating and managing Jira post-mortems."""

    def __init__(self) -> None:
        self.client = JiraClient()
        self.project_key = getattr(
            settings, "JIRA_POSTMORTEM_PROJECT_KEY", "INCIDENT"
        )
        self.issue_type = getattr(settings, "JIRA_POSTMORTEM_ISSUE_TYPE", "Post-mortem")
        self.field_ids = getattr(
            settings,
            "JIRA_POSTMORTEM_FIELDS",
            {
                "incident_summary": "customfield_12699",
                "timeline": "customfield_12700",
                "root_causes": "customfield_12701",
                "impact": "customfield_12702",
                "mitigation_actions": "customfield_12703",
                "incident_category": "customfield_12369",
            },
        )

    def create_postmortem_for_incident(
        self,
        incident: Incident,
        created_by: User | None = None,
    ) -> JiraPostMortem:
        """Create a Jira post-mortem for an incident.

        Args:
            incident: Incident to create post-mortem for
            created_by: User creating the post-mortem

        Returns:
            JiraPostMortem instance

        Raises:
            ValueError: If incident already has a Jira post-mortem
            JiraAPIError: If Jira API call fails
        """
        if hasattr(incident, "jira_postmortem_for"):
            error_msg = f"Incident #{incident.id} already has a Jira post-mortem"
            raise ValueError(error_msg)

        logger.info(f"Creating Jira post-mortem for incident #{incident.id}")

        # Prefetch incident updates and jira_ticket for timeline and parent link
        from firefighter.incidents.models.incident import Incident  # noqa: PLC0415

        incident = (
            Incident.objects.select_related("priority", "environment", "jira_ticket")
            .prefetch_related("incidentupdate_set")
            .get(pk=incident.pk)
        )

        # Generate content from templates
        fields = self._generate_issue_fields(incident)

        # Get parent issue key from RAID Jira ticket if available
        parent_issue_key = None
        if hasattr(incident, "jira_ticket") and incident.jira_ticket:
            parent_issue_key = incident.jira_ticket.key

        # Create Jira issue with optional parent link
        jira_issue = self.client.create_postmortem_issue(
            project_key=self.project_key,
            issue_type=self.issue_type,
            fields=fields,
            parent_issue_key=parent_issue_key,
        )

        # Assign to incident commander if available
        commander = incident.roles_set.filter(role_type__slug="commander").first()
        if (
            commander
            and hasattr(commander.user, "jira_user")
            and commander.user.jira_user is not None
        ):
            assigned = self.client.assign_issue(
                issue_key=jira_issue["key"],
                account_id=commander.user.jira_user.id,
            )
            if assigned:
                logger.info(
                    "Assigned post-mortem %s to commander %s",
                    jira_issue["key"],
                    commander.user.username,
                )

        # Create JiraPostMortem record
        jira_postmortem = JiraPostMortem.objects.create(
            incident=incident,
            jira_issue_key=jira_issue["key"],
            jira_issue_id=jira_issue["id"],
            created_by=created_by,
        )

        logger.info(
            f"Created Jira post-mortem {jira_postmortem.jira_issue_key} "
            f"for incident #{incident.id}"
        )

        return jira_postmortem

    def _generate_issue_fields(self, incident: Incident) -> dict[str, str | dict[str, str]]:
        """Generate Jira issue fields from incident data.

        Args:
            incident: Incident to generate fields for

        Returns:
            Dictionary of Jira field IDs to values
        """
        # Generate summary (standard field)
        env = getattr(settings, "ENV", "dev")
        topic_prefix = "" if env in {"support", "prod"} else f"[IGNORE - TEST {env}] "
        summary = (
            f"{topic_prefix}#{incident.slack_channel_name} "
            f"({incident.priority.name}) {incident.title}"
        )

        # Generate content from Django templates (Jira Wiki Markup)
        context = {
            "incident": incident,
            "priority": incident.priority,
            "created_at": incident.created_at,
            "components": [],  # No component relationship available
        }

        incident_summary = render_to_string(
            "jira/postmortem/incident_summary.txt",
            context,
        )

        timeline = render_to_string(
            "jira/postmortem/timeline.txt",
            context,
        )

        impact = render_to_string(
            "jira/postmortem/impact.txt",
            context,
        )

        mitigation_actions = render_to_string(
            "jira/postmortem/mitigation_actions.txt",
            context,
        )

        # Optional: root causes (editable placeholder for manual completion)
        root_causes = render_to_string(
            "jira/postmortem/root_causes.txt",
            context,
        )

        # Build field mapping
        fields: dict[str, str | dict[str, str]] = {
            "summary": summary,
            self.field_ids["incident_summary"]: incident_summary,
            self.field_ids["timeline"]: timeline,
            self.field_ids["impact"]: impact,
            self.field_ids["mitigation_actions"]: mitigation_actions,
        }

        # Add optional fields if not empty
        if root_causes.strip():
            fields[self.field_ids["root_causes"]] = root_causes

        # Add incident category if available
        if incident.incident_category:
            # Jira select field requires dict with value key
            category_field_id = self.field_ids["incident_category"]
            fields[category_field_id] = {"value": incident.incident_category.name}

        return fields


# Singleton instance
jira_postmortem_service = JiraPostMortemService()
