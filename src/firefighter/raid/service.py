from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from firefighter.jira_app.client import (
    JiraAPIError,
    JiraUserNotFoundError,
)
from firefighter.jira_app.models import JiraUser
from firefighter.raid.client import client as jira_client
from firefighter.raid.models import QualifierRotation

if TYPE_CHECKING:
    from firefighter.incidents.models.user import User
    from firefighter.raid.types import JiraObject


logger = logging.getLogger(__name__)
RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID
error_jira_ticket_creation = "Could not create Jira ticket"


def check_issue_id(issue: JiraObject, title: str, reporter: str) -> int | str:
    issue_id = issue.get("id")
    if issue_id is None:
        logger.error(
            f"Could not create Jira ticket for the incident {title} and the reporter {reporter}"
        )
        raise JiraAPIError(error_jira_ticket_creation)
    return issue_id


def get_current_qualifier() -> JiraUser:
    """Returns the qualifier Jira account id for today. On weekends use Qraft generic account.

    Returns:
        JiraUser: JiraUser object
    """
    if timezone.now().date().weekday() in {5, 6}:
        return jira_client.get_jira_user_from_jira_id(RAID_DEFAULT_JIRA_QRAFT_USER_ID)
    try:
        qualifier_rotation = QualifierRotation.objects.get(day=timezone.now().date())
    except QualifierRotation.DoesNotExist:
        logger.warning("Qualifier rotation not found for today.")
        return jira_client.get_jira_user_from_jira_id(RAID_DEFAULT_JIRA_QRAFT_USER_ID)
    return qualifier_rotation.jira_user


def get_jira_user_from_user(user: User) -> JiraUser:
    """Returns the JiraUser object for a given user, if it exists in DB or can be fetched on Jira API. Returns the default JiraUser if not found."""
    try:
        jira_user = jira_client.get_jira_user_from_user(user)
    except JiraAPIError:
        logger.exception(f"Could not find Jira user for {user.id}")

        logger.warning(f"User {user.id} has no Jira user")
        try:
            jira_user = jira_client.get_jira_user_from_jira_id(
                RAID_DEFAULT_JIRA_QRAFT_USER_ID
            )
        except JiraUserNotFoundError:
            logger.exception(
                f"Could not find Jira user with account id {RAID_DEFAULT_JIRA_QRAFT_USER_ID}"
            )
            jira_user = JiraUser.objects.get(id=RAID_DEFAULT_JIRA_QRAFT_USER_ID)
    return jira_user


def create_issue_feature_request(
    title: str,
    description: str,
    reporter: str,
    priority: int | None,
    labels: list[str] | None,
    platform: str,
) -> JiraObject:
    """Creates a Jira issue of type Feature Request.

    Args:
        title (str): Summary of the issue
        description (str): Description of the issue
        reporter (str): Jira account id of the reporter
        priority (int): Priority of the issue
        labels (list[str]): Labels to add to the issue
        platform (str): Platform of the issue
    """
    if labels is None:
        labels = [""]
    if "feature-request" not in labels:
        labels.append("feature-request")
    issue = jira_client.create_issue(
        issuetype="Feature Request",
        summary=title,
        description=description,
        assignee=get_current_qualifier().id,
        reporter=reporter,
        qualifier=get_current_qualifier().id,
        priority=priority,
        labels=labels,
        platform=platform,
    )
    check_issue_id(issue, title=title, reporter=reporter)
    return issue


def create_issue_documentation_request(
    title: str,
    description: str,
    reporter: str,
    priority: int | None,
    labels: list[str] | None,
    platform: str,
) -> JiraObject:
    """Creates a Jira issue of type Documentation/Process Request.

    Args:
        title (str): Summary of the issue
        description (str): Description of the issue
        reporter (str): Jira account id of the reporter
        priority (int): Priority of the issue
        labels (list[str]): Labels to add to the issue
        platform (str): Platform of the issue
    """
    if labels is None:
        labels = [""]
    if "documentation-request" not in labels:
        labels.append("documentation-request")
    issue = jira_client.create_issue(
        issuetype="Documentation/Process Request",
        summary=title,
        description=description,
        assignee=get_current_qualifier().id,
        reporter=reporter,
        qualifier=get_current_qualifier().id,
        priority=priority,
        labels=labels,
        platform=platform,
    )
    check_issue_id(issue, title=title, reporter=reporter)
    return issue


def create_issue_internal(
    title: str,
    description: str,
    reporter: str,
    priority: int | None,
    labels: list[str] | None,
    platform: str,
    business_impact: str | None,
    team_to_be_routed: str | None,
    area: str | None,
) -> JiraObject:
    """Creates a Jira Incident Issue of type Internal.

    Args:
        title (str): Summary of the issue
        description (str): Description of the issue
        reporter (str): Jira account id of the reporter
        priority (int): Priority of the issue
        labels (list[str]): Labels to add to the issue
        platform (str): Platform of the issue
        business_impact (str): Business impact of the issue
        team_to_be_routed (str): Team to be routed
        area (str): Area of the issue
    """
    issue = jira_client.create_issue(
        issuetype="Incident",
        summary=title,
        description=description,
        assignee=get_current_qualifier().id,
        reporter=reporter,
        qualifier=get_current_qualifier().id,
        priority=priority,
        labels=labels,
        platform=platform,
        business_impact=business_impact,
        suggested_team_routing=team_to_be_routed,
        area=area,
    )
    check_issue_id(issue, title=title, reporter=reporter)
    return issue


def create_issue_customer(
    title: str,
    description: str,
    reporter: str,
    priority: int | None,
    labels: list[str] | None,
    platform: str,
    business_impact: str | None,
    team_to_be_routed: str | None,
    area: str | None,
    zendesk_ticket_id: str | None,
) -> JiraObject:
    """Creates a Jira Incident issue of type Customer.

    Args:
        title (str): Summary of the issue
        description (str): Description of the issue
        reporter (str): Jira account id of the reporter
        priority (int): Priority of the issue
        labels (list[str]): Labels to add to the issue
        platform (str): Platform of the issue
        business_impact (str): Business impact of the issue
        team_to_be_routed (str): Team to be routed
        area (str): Area of the issue
        zendesk_ticket_id (str): Zendesk ticket id
    """
    issue = jira_client.create_issue(
        issuetype="Incident",
        summary=title,
        description=description,
        assignee=get_current_qualifier().id,
        reporter=reporter,
        qualifier=get_current_qualifier().id,
        priority=priority,
        labels=labels,
        platform=platform,
        business_impact=business_impact,
        suggested_team_routing=team_to_be_routed,
        area=area,
        zendesk_ticket_id=zendesk_ticket_id,
    )
    check_issue_id(issue, title=title, reporter=reporter)
    return issue


def create_issue_seller(  # noqa: PLR0913, PLR0917
    title: str,
    description: str,
    reporter: str,
    priority: int | None,
    labels: list[str] | None,
    platform: str,
    business_impact: str | None,
    team_to_be_routed: str | None,
    area: str | None,
    seller_contract_id: str | None,
    is_key_account: bool | None,  # noqa: FBT001
    is_seller_in_golden_list: bool | None,  # noqa: FBT001
    zoho_desk_ticket_id: str | None,
) -> JiraObject:
    """Creates a Jira Incident issue of type Seller.

    Args:
        title (str): Summary of the issue
        description (str): Description of the issue
        reporter (str): Jira account id of the reporter
        priority (int): Priority of the issue
        labels (list[str]): Labels to add to the issue
        platform (str): Platform of the issue
        business_impact (str): Business impact of the issue
        team_to_be_routed (str): Team to be routed
        area (str): Area of the issue
        seller_contract_id (str): Seller contract id
        is_key_account (bool): Is key account
        is_seller_in_golden_list (bool): Is seller in golden list
        zoho_desk_ticket_id (str): Zoho desk ticket id
    """
    issue = jira_client.create_issue(
        issuetype="Incident",
        summary=title,
        description=description,
        assignee=get_current_qualifier().id,
        reporter=reporter,
        qualifier=get_current_qualifier().id,
        priority=priority,
        labels=labels,
        platform=platform,
        business_impact=business_impact,
        suggested_team_routing=team_to_be_routed,
        area=area,
        seller_contract_id=seller_contract_id,
        is_key_account=is_key_account,
        is_seller_in_golden_list=is_seller_in_golden_list,
        zoho_desk_ticket_id=zoho_desk_ticket_id,
    )
    check_issue_id(issue, title=title, reporter=reporter)
    return issue
