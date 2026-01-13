"""Service for creating and managing Jira post-mortems."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.template.loader import render_to_string

from firefighter.jira_app.client import (
    JiraClient,
    JiraUserDatabaseError,
    JiraUserNotFoundError,
)
from firefighter.jira_app.models import JiraPostMortem

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


class JiraPostMortemService:
    """Service for creating and managing Jira post-mortems."""

    def __init__(self) -> None:
        self.client = JiraClient()
        self.project_key = getattr(settings, "JIRA_POSTMORTEM_PROJECT_KEY", "INCIDENT")
        self.issue_type = getattr(settings, "JIRA_POSTMORTEM_ISSUE_TYPE", "Post-mortem")
        self.ready_status_name = getattr(
            settings, "JIRA_POSTMORTEM_READY_STATUS", "Ready"
        )
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
        commander = (
            incident.roles_set.select_related("user__jira_user", "role_type")
            .filter(role_type__slug="commander")
            .first()
        )
        if commander:
            jira_user = getattr(commander.user, "jira_user", None)
            if jira_user is None:
                try:
                    jira_user = self.client.get_jira_user_from_user(commander.user)
                except (JiraUserNotFoundError, JiraUserDatabaseError) as exc:
                    logger.warning(
                        "Unable to fetch Jira user for commander %s: %s",
                        commander.user_id,
                        exc,
                    )
            if jira_user is not None:
                assigned = self.client.assign_issue(
                    issue_key=jira_issue["key"],
                    account_id=jira_user.id,
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

    def is_postmortem_ready(self, jira_postmortem: JiraPostMortem) -> tuple[bool, str]:
        """Check if the Jira post-mortem issue is in the Ready status.

        Returns:
            Tuple of (is_ready, current_status_name)
        """
        issue = self.client.jira.issue(jira_postmortem.jira_issue_id)
        status_name: str = getattr(issue.fields.status, "name", "")
        return status_name == self.ready_status_name, status_name

    def _generate_issue_fields(
        self, incident: Incident
    ) -> dict[str, str | dict[str, str] | list[dict[str, str]]]:
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
        fields: dict[str, str | dict[str, str] | list[dict[str, str]]] = {
            "summary": summary,
            self.field_ids["incident_summary"]: incident_summary,
            self.field_ids["timeline"]: timeline,
            self.field_ids["impact"]: impact,
            self.field_ids["mitigation_actions"]: mitigation_actions,
        }

        due_date = self._add_business_days(incident.created_at, 40).date()
        fields["duedate"] = due_date.isoformat()

        # Add optional fields if not empty
        if root_causes.strip():
            fields[self.field_ids["root_causes"]] = root_causes

        # Add incident category if available
        if incident.incident_category:
            # Jira select field requires dict with value key
            category_field_id = self.field_ids["incident_category"]
            fields[category_field_id] = {"value": incident.incident_category.name}

        # Replicate custom fields from incident ticket to post-mortem
        self._add_replicated_custom_fields(incident, fields)

        return fields

    def _add_replicated_custom_fields(
        self,
        incident: Incident,
        fields: dict[str, str | dict[str, str] | list[dict[str, str]]],
    ) -> None:
        """Replicate custom fields from incident ticket to post-mortem.

        Replicates the following fields from the incident ticket:
        - Priority (customfield_11064)
        - Affected environments (customfield_11049)
        - Zoho desk ticket (customfield_10896)
        - Zendesk ticket (customfield_10895)
        - Seller Contract ID (customfield_10908)
        - Platforms (customfield_10201) - first platform from list
        - Business Impact (customfield_10936)

        Args:
            incident: Incident to extract fields from
            fields: Dictionary to add fields to (modified in place)
        """
        custom_fields = incident.custom_fields or {}

        # Priority - customfield_11064 (option field)
        if incident.priority:
            priority_value = str(incident.priority.value)
            fields["customfield_11064"] = {"value": priority_value}

        # Affected environments - customfield_11049 (array field)
        environments = custom_fields.get("environments", [])
        if environments:
            fields["customfield_11049"] = [{"value": env} for env in environments]

        # Zendesk ticket - customfield_10895 (string field)
        zendesk_ticket_id = custom_fields.get("zendesk_ticket_id")
        if zendesk_ticket_id:
            fields["customfield_10895"] = str(zendesk_ticket_id)

        # Zoho desk ticket - customfield_10896 (string field)
        zoho_desk_ticket_id = custom_fields.get("zoho_desk_ticket_id")
        if zoho_desk_ticket_id:
            fields["customfield_10896"] = str(zoho_desk_ticket_id)

        # Seller Contract ID - customfield_10908 (string field)
        seller_contract_id = custom_fields.get("seller_contract_id")
        if seller_contract_id:
            fields["customfield_10908"] = str(seller_contract_id)

        # Platform - customfield_10201 (option field)
        platforms = custom_fields.get("platforms", [])
        if platforms:
            # Extract first platform and remove "platform-" prefix if present
            platform = platforms[0] if isinstance(platforms, list) else platforms
            platform_value = platform.replace("platform-", "") if isinstance(platform, str) else platform
            fields["customfield_10201"] = {"value": platform_value}

        # Business Impact - customfield_10936 (option field)
        # Business impact is stored in the Jira ticket, not in custom_fields
        if hasattr(incident, "jira_ticket") and incident.jira_ticket:
            business_impact = incident.jira_ticket.business_impact
            if business_impact and business_impact not in {"", "N/A"}:
                fields["customfield_10936"] = {"value": business_impact}

    @staticmethod
    def _add_business_days(start: datetime, days: int) -> datetime:
        current = start
        added = 0
        while added < days:
            current += timedelta(days=1)
            if current.weekday() < 5:
                added += 1
        return current


# Singleton instance
jira_postmortem_service = JiraPostMortemService()
