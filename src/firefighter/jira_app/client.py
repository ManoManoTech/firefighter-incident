from __future__ import annotations

import logging
import time
import urllib.parse
from functools import cached_property
from typing import Any, cast

from django import db
from django.conf import settings
from jira import JIRA, exceptions
from jira import User as JiraAPIUser

from firefighter.incidents.models.user import User
from firefighter.jira_app.models import JiraUser
from firefighter.jira_app.types import (
    Status,
    StatusTransitionInfo,
    Transition,
    WorkflowBuilderResponse,
)
from firefighter.jira_app.utils import (
    get_status_id_from_name,
    get_transitions_to_apply,
    pythonic_keys,
)

logger = logging.getLogger(__name__)


RAID_JIRA_API_URL: str = settings.RAID_JIRA_API_URL


class JiraUserNotFoundError(Exception):
    pass


class JiraUserDatabaseError(Exception):
    pass


class JiraAPIError(Exception):
    pass


class SlackNotificationError(Exception):
    pass


class GetWatchersError(Exception):
    pass


class GetReporterError(Exception):
    pass


class JiraClient:
    def __init__(self) -> None:
        self.url = RAID_JIRA_API_URL

    @cached_property
    def jira(self) -> JIRA:
        return JIRA(
            server=self.url,
            basic_auth=(
                settings.RAID_JIRA_API_USER,
                settings.RAID_JIRA_API_PASSWORD,
            ),
            options={"headers": settings.FF_HTTP_CLIENT_ADDITIONAL_HEADERS or {}},
        )

    def transition_issue_auto(
        self, issue_id: str | int, target_status_name: str, workflow_name: str
    ) -> None:
        """Attempts to close an issue by applying transitions to it.

        Args:
            issue_id (str | int): Jira issue id
            target_status_name (str): target status name
            workflow_name (str): workflow name
        """
        issue_id = str(issue_id)
        transitions_info = self._get_transitions(
            self._get_project_config_workflow_from_builder_base(workflow_name)
        )
        if len(transitions_info) == 0:
            logger.error(
                f"Could not find transitions for issue id={issue_id}! Not closing issue."
            )

        # Get closed state id
        # XXX Use a list of closed states to support multiple workflows, or better
        closed_state_id = get_status_id_from_name(transitions_info, target_status_name)
        if closed_state_id is None:
            logger.warning(
                f"Could not find target status '{target_status_name}' id for issue {issue_id}! Not closing issue."
            )
            return

        # Get current issue status
        issue = self.jira.issue(issue_id)
        current_status_id = int(issue.fields.status.id)

        # Get transitions to apply
        transitions_to_apply = get_transitions_to_apply(
            current_status_id, transitions_info, closed_state_id
        )

        if len(transitions_to_apply) == 0:
            logger.info(f"Issue {issue_id} is already closed. Not closing again.")

        # Apply transitions
        # XXX Better error handling
        for transition in transitions_to_apply:
            logger.debug(f"Running transition: {transition}")
            self.jira.transition_issue(
                issue=issue_id,
                transition=transition,
                fields={},
            )

    def _fetch_jira_user(self, username: str) -> JiraAPIUser:
        """Fetches a Jira user from the Jira API.

        Args:
            username (str): username of the Jira user (e.g. john.doe)

        Raises:
            ValueError: Empty username
            JiraUserNotFoundError: User not found in Jira

        Returns:
            JiraAPIUser: Jira API user object
        """
        if username is None or username == "":
            invalid_username_log = f"Invalid username '{username}'"
            raise ValueError(invalid_username_log)
        response = self.jira.search_users(query=username)
        if len(response) == 0:
            raise JiraUserNotFoundError("User not found in Jira.")
        if len(response) > 1:
            # Get the first user that matches the email address
            jira_user = next(
                (
                    user
                    for user in response
                    if user.raw.get("emailAddress", "a@b").split("@")[0] == username
                ),
                None,
            )
            if jira_user is None:
                err_msg = f"More than one JIRA user found for username '{username}'."
                raise JiraUserNotFoundError(err_msg)
            return jira_user
        return response[0]

    def get_jira_user_from_user(self, user: User) -> JiraUser:
        """Fetches a Jira user from the Jira API.

        Args:
            user (User): User object

        Raises:
            JiraUserNotFoundError: User not found in Jira

        Returns:
            JiraAPIUser: Jira API user object
        """
        # Check if user has a Jira user
        if hasattr(user, "jira_user") and user.jira_user:
            return user.jira_user

        username = user.email.split("@")[0]
        jira_user = self._fetch_jira_user(username)

        return JiraUser.objects.update_or_create(
            id=jira_user.raw.get("accountId"), defaults={"user": user}
        )[0]

    def get_jira_user_from_jira_id(self, jira_account_id: str) -> JiraUser:
        """Look for a Jira User in DB, if not found, fetch it from Jira API.

        Args:
            jira_account_id (str): Jira account id

        Raises:
            JiraUserNotFoundError: User not found in Jira nor in DB
            JiraUserDatabaseError: Unable to create user in DB
            ValueError: Empty jira_account_id

        Returns:
            JiraUser: Jira user object
        """
        if jira_account_id is None or jira_account_id == "":
            err_msg = f"Jira account id is empty ('{jira_account_id}')"
            raise ValueError(err_msg)

        # Look in the DB
        try:
            return JiraUser.objects.get(id=jira_account_id)
        except JiraUser.DoesNotExist:
            logger.debug(
                f"Jira user {jira_account_id} not found in DB, fetching from Jira API"
            )
        logger.info("User %s not found in DB. Check sync user task.", jira_account_id)

        # Look on JIRA API
        jira_api_user, email = self._get_user_from_api(jira_account_id)

        username: str = email.split("@")[0]
        # Check if we have user with same email
        try:
            user: User = User.objects.select_related("jira_user").get(email=email)
            if (
                hasattr(user, "jira_user")
                and user.jira_user
                and isinstance(user.jira_user, JiraUser)
            ):
                return user.jira_user
            try:
                return JiraUser.objects.create(
                    id=jira_account_id,
                    user=user,
                )
            except db.IntegrityError as e:
                logger.exception("Error creating user %s", jira_account_id)
                raise JiraUserDatabaseError("Unable to create user") from e

        except User.DoesNotExist:
            logger.warning("User %s not found in DB. Creating it...", jira_account_id)
            user = self._create_user_from_jira_info(
                jira_account_id, jira_api_user, email, username
            )

        try:
            return JiraUser.objects.create(
                id=jira_account_id,
                user=user,
            )
        except db.IntegrityError as e:
            logger.exception("Error creating user %s", jira_account_id)
            raise JiraUserDatabaseError("Unable to create user") from e

    def get_watchers_from_jira_ticket(
        self, jira_issue_id: int | str
    ) -> list[JiraAPIUser]:
        """Fetch watchers for a specific Jira ticket from Jira API.

        Args:
            jira_issue_id (str | int): Jira issue id

        Raises:
            ValueError: Empty issue id

        Returns:
            list(JiraAPIUser): List of Jira users object
        """
        watchers = self.jira.watchers(jira_issue_id).raw.get("watchers")
        if len(watchers) == 0:
            logger.warning(
                "Watchers not found for jira_account_id '%s'.", jira_issue_id
            )
        return watchers

    @staticmethod
    def _create_user_from_jira_info(
        jira_account_id: str,
        jira_api_user: JiraAPIUser,
        email: str,
        username: str,
    ) -> User:
        name = jira_api_user.raw.get("displayName")
        if not name or not isinstance(name, str):
            logger.warning("User %s has no display name, using email as name", email)
            name = email.split("@", maxsplit=1)[0]
        try:
            user: User = User.objects.create(
                name=name,
                email=email,
                username=username,
            )

        except db.IntegrityError as e:
            logger.exception("Error creating user %s", jira_account_id)
            raise JiraUserDatabaseError("Unable to create user") from e
        return user

    def _get_user_from_api(self, jira_account_id: str) -> tuple[JiraAPIUser, str]:
        try:
            jira_api_user = self.jira.user(jira_account_id)
            email: str | None = jira_api_user.raw.get("emailAddress")

        except exceptions.JIRAError as e:
            logger.exception("Error getting user %s", jira_account_id)
            raise JiraUserNotFoundError("User not Found") from e

        if email is None:
            logger.warning("User %s has no email address", jira_account_id)
            raise JiraUserNotFoundError("User not Found: no email address for user")
        return jira_api_user, email

    def _get_project_config_workflow_base(
        self, project_key: str, workflow_name: str
    ) -> dict[str, Any]:
        """This is an undocumented API. Make sure your error handling is robust."""
        ts_ms = int(time.time() * 1000)
        # XXX Incident workflow name resolution
        # XXX Check if INCIDENT is configured the same way, try to get it dynamically
        workflow_name_url_encoded = urllib.parse.quote_plus(workflow_name)

        get_workflow = f"/rest/projectconfig/latest/workflow?projectKey={project_key}&workflowName={workflow_name_url_encoded}&_={ts_ms}"
        url = f"{self.jira.server_url}{get_workflow}"

        # XXX Try catch
        # XXX Override Jira Class / split client and service
        return cast(
            "dict[str, Any]",
            self.jira._session.get(  # noqa: SLF001
                url,
                headers=self.jira._options["headers"],  # noqa: SLF001
            ).json(),
        )

    def _get_project_config_workflow_from_builder_base(
        self, workflow_name: str
    ) -> WorkflowBuilderResponse:
        ts_ms = int(time.time() * 1000)
        # XXX Incident workflow name resolution
        # XXX Check if INCIDENT is configured the same way, try to get it dynamically
        workflow_name_url_encoded = urllib.parse.quote_plus(workflow_name)

        get_workflow = f"/rest/workflowDesigner/latest/workflows?name={workflow_name_url_encoded}&_={ts_ms}&draft=false"
        url = f"{self.jira.server_url}{get_workflow}"

        # XXX Try catch
        # XXX Override Jira Class / split client and service
        res = self.jira._session.get(  # noqa: SLF001
            url,
            headers=self.jira._options["headers"],  # noqa: SLF001
        ).json()
        statuses: list[dict[str, Any]] = res["layout"]["statuses"]
        transitions: list[dict[str, Any]] = res["layout"]["transitions"]
        statuses = pythonic_keys(statuses)
        transitions = pythonic_keys(transitions)
        for transition in transitions:
            # XXX: Ugly, make a helper and make sure it's safe
            transition["source_id"] = int(
                transition["source_id"]
                .replace("S<", "")
                .replace(">", "")
                .replace("I<", "")
            )
            transition["target_id"] = int(
                transition["target_id"]
                .replace("S<", "")
                .replace(">", "")
                .replace("I<", "")
            )
            if "source_angle" in transition:
                del transition["source_angle"]
            if "target_angle" in transition:
                del transition["target_angle"]

        for status in statuses:
            status["id"] = int(
                status["id"].replace("S<", "").replace(">", "").replace("I<", "")
            )
            if "x" in status:
                del status["x"]
            if "y" in status:
                del status["y"]

        return WorkflowBuilderResponse(
            statuses=cast("list[Status]", statuses),
            transitions=cast("list[Transition]", transitions),
        )

    @staticmethod
    def _get_transitions(
        workflow_builder_response: WorkflowBuilderResponse,
    ) -> list[StatusTransitionInfo]:
        statuses_info_list: list[StatusTransitionInfo] = []

        statuses: list[Status] = workflow_builder_response["statuses"]
        transitions: list[Transition] = workflow_builder_response["transitions"]

        step_id_to_status_id: dict[int, int] = {
            status["step_id"]: int(status.get("status_id", status["step_id"]))
            for status in statuses
        }
        status_id_to_name: dict[int, str] = {
            step_id_to_status_id[status["step_id"]]: status["name"]
            for status in statuses
        }

        for transition in transitions:
            if "screen_name" in transition:
                logger.debug(
                    "Ignoring Transition %s has a screen_name: %s",
                    transition["name"],
                    transition["screen_name"],
                )
                continue  # Ignore transitions that have a screen_name
            if transition["initial"]:
                logger.debug(f"Ignoring Transition {transition['name']} is initial")
                continue

            source_id = step_id_to_status_id[transition["source_id"]]
            target_id = step_id_to_status_id[transition["target_id"]]

            if (
                source_id not in step_id_to_status_id.values()
                or target_id not in step_id_to_status_id.values()
            ):
                logger.info(
                    f"Ignoring Transition {transition['name']} has invalid status: {source_id} and {target_id} not in {step_id_to_status_id}"
                )
                continue  # Ignore transitions that refer to non-existent statuses

            # Prepare _StatusTransitionInfo
            status_transition_info: StatusTransitionInfo = {
                "status_id": source_id,
                "status_name": status_id_to_name[source_id],
                "target_statuses": {target_id},
                "transition_to_status": {target_id: transition["name"]},
            }

            # Check if the status already exists in the list
            for existing_info in statuses_info_list:
                if existing_info["status_id"] == source_id:
                    existing_info["target_statuses"].add(target_id)
                    existing_info["transition_to_status"][target_id] = transition[
                        "name"
                    ]
                    break
            else:
                # If the status doesn't exist in the list, add the new info
                statuses_info_list.append(status_transition_info)

        # For global transitions, add the transition to all statuses
        for transition in transitions:
            if transition["global_transition"]:
                for status_info in statuses_info_list:
                    status_info["target_statuses"].add(
                        step_id_to_status_id[int(transition["target_id"])]
                    )
                    status_info["transition_to_status"][
                        step_id_to_status_id[int(transition["target_id"])]
                    ] = transition["name"]

        return statuses_info_list


client = JiraClient()
