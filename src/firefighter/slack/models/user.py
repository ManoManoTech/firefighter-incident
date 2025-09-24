from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urljoin

import slack_sdk.errors
from django.db import models
from django.db.utils import IntegrityError
from django.utils import timezone
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.firefighter.utils import get_in
from firefighter.incidents.models.user import User
from firefighter.slack.slack_app import DefaultWebClient, SlackApp, slack_client

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from slack_sdk.web.client import WebClient
    from slack_sdk.web.slack_response import SlackResponse

    from firefighter.slack.messages.base import SlackMessageSurface


logger = logging.getLogger(__name__)


class SlackUserManager(models.Manager["SlackUser"]):
    def get_or_none(self, **kwargs: Any) -> SlackUser | None:
        try:
            return self.get(**kwargs)
        except SlackUser.DoesNotExist:
            return None

    @slack_client
    def get_user_by_slack_id(
        self,
        slack_id: str,
        defaults: dict[str, str] | None = None,
        client: WebClient = DefaultWebClient,
    ) -> User | None:
        """Returns a User from DB if it exists, or fetch its info from Slack, save it to DB and returns it."""
        if not slack_id:
            raise ValueError("slack_id cannot be empty")

        # Try fetching it from DB...
        try:
            slack_user = self.select_related("user").get(slack_id=slack_id)
            return slack_user.user  # noqa: TRY300
        except SlackUser.DoesNotExist:
            slack_user = None

        if (
            defaults
            and "email" in defaults
            and "name" in defaults
            and defaults["name"]
            and defaults["email"]
        ):
            user, _ = User.objects.get_or_create(
                username=defaults["email"].split("@")[0],
                email=defaults["email"],
                defaults={"name": defaults["name"]},
            )
            slack_user, _created = SlackUser.objects.get_or_create(
                slack_id=slack_id, user=user, defaults={"id": uuid.uuid4()}
            )
            return user

        # If not in DB, fetch the user's info from firefighter.slack...
        logger.debug("Fetch user from Slack")
        try:
            user_info = client.users_info(user=slack_id)
            if not user_info.get("ok"):
                logger.error("Could not fetch user from firefighter.slack.")
                return None
        except slack_sdk.errors.SlackApiError:
            logger.exception(f"Could not find Slack user with ID: {slack_id}")
            return None

        clean_user_info = self.unpack_user_info(user_info=user_info)

        if "email" not in clean_user_info and "display_name" not in clean_user_info:
            logger.error(
                f"Not enough info in Slack user.info response! user_info: {user_info}, parsed: {clean_user_info}"
            )
            return None
        user, _ = User.objects.get_or_create(
            username=clean_user_info["email"].split("@")[0],
            email=clean_user_info["email"],
            defaults={"name": clean_user_info["name"]},
        )
        if user is None:
            raise ValueError("Could not create user from Slack info")

        # TODO Handle case of user but with outdated email
        logger.debug("Creating Slack user")
        logger.debug(user_info)
        slack_user, _ = self.get_or_create_from_slack(user_info=user_info, user=user)
        if not slack_user:
            logger.error("Could not upsert slack_user in DB WTF")
            return None

        return user

    @slack_client
    def upsert_by_email(
        self,
        email: str,
        client: WebClient = DefaultWebClient,
    ) -> User | None:
        """Returns a User from DB if it exists, or fetch its info from Slack, save it to DB and returns it."""
        logger.debug(f"Looking for user by email: {email}")
        # Try fetching it from DB...
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logger.info("No user in DB. Fetching it from Slack...")
        else:
            return user

        # If not in DB, fetch the user's info from firefighter.slack...
        try:
            user_info = client.users_lookupByEmail(email=email)
            if not user_info.get("ok"):
                logger.error(f"Could not fetch user from Slack. User: email={email}")
                return None
        except slack_sdk.errors.SlackApiError:
            logger.exception(f"Could not find Slack user with email: {email}")
            return None

        logger.debug(user_info)

        clean_user_info = self.unpack_user_info(user_info=user_info)

        slack_user = SlackUser.objects.get_or_none(slack_id=clean_user_info["slack_id"])

        # If we have a SlackUser but not user with email => Update user email
        if slack_user:
            user = slack_user.user
            user.email = email
            user.save()
            return user

        # If we have no Slack User, let's go ahead and create a User and its associated SlackUser
        user, _created = User.objects.get_or_create(
            email=email,
            username=email.split("@", maxsplit=1)[0],
            defaults={
                "name": clean_user_info["name"],
            },
        )

        try:
            slack_user, _created = self.get_or_create_from_slack(
                user_info=user_info,
                slack_id=clean_user_info["slack_id"],
                defaults={"user_id": user.id, "id": uuid.uuid4()},
            )
            if slack_user and slack_user.user.email == email:
                return user
            logger.warning(f"1. Change of mail for user: {clean_user_info['slack_id']}")

        except IntegrityError:
            logger.warning(
                f"2. Change of mail for user: {clean_user_info['slack_id']}",
                exc_info=True,
            )
            slack_user, _created = self.get_or_create_from_slack(
                user_info=user_info,
                user_id=user.id,
                defaults={"slack_id": clean_user_info["slack_id"], "id": uuid.uuid4()},
            )
            return user
        return None

    @slack_client
    def add_slack_id_to_user(
        self,
        user: User,
        client: WebClient = DefaultWebClient,
    ) -> User | None:
        if hasattr(user, "slack_user") and user.slack_user and user.slack_user.slack_id:
            return user

        if not user.email:
            logger.warning(
                f"Can't search Slack ID for user {user} because it has no email!"
            )
            return None

        # If not in DB, fetch the user's info from firefighter.slack...
        try:
            user_info = client.users_lookupByEmail(email=user.email)
        except slack_sdk.errors.SlackApiError:
            logger.exception(f"Could not find Slack user with email: {user.email}")
            return None

        if not user_info.get("ok"):
            logger.error(
                f"Could not fetch user from firefighter.slack. User: email={user.email}"
            )
            return None

        user_id = get_in(user_info, "user.id")

        slack_user, created = self.get_or_create_from_slack(
            user_info=user_info, slack_id=user_id, defaults={"user": user}
        )
        if created:
            slack_user.save()
        return user

    def get_or_create_from_slack(
        self,
        user_info: SlackResponse | dict[str, Any],
        defaults: MutableMapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[Any, bool]:
        # Get all info abt someone
        clean_user_info = self.unpack_user_info(user_info)

        # Remove info that could be in kwargs (we do not want them in the defaults too)
        if kwargs.get("slack_id"):
            clean_user_info.pop("slack_id", None)

        merged_defaults = (
            {**clean_user_info, **defaults} if defaults else clean_user_info
        )

        # Remove the email, not wanted in the defaults (no email field on SlackUser)
        # TODO Remove all dict keys that are not fields of the SlackUser
        if "email" in merged_defaults:
            del merged_defaults["email"]
        if "name" in merged_defaults:
            del merged_defaults["name"]
        if "first_name" in merged_defaults:
            del merged_defaults["first_name"]
        if "last_name" in merged_defaults:
            del merged_defaults["last_name"]
        if "deleted" in merged_defaults:
            del merged_defaults["deleted"]
        return SlackUser.objects.get_or_create(defaults=merged_defaults, **kwargs)

    def update_or_create_from_slack_info(
        self, user_info: dict[str, Any]
    ) -> User | None:
        clean_user_info = self.unpack_user_info(user_info=user_info)

        if "email" not in clean_user_info and "display_name" not in clean_user_info:
            logger.error(
                f"Not enough info in Slack user.info response! user_info: {user_info}, parsed: {clean_user_info}"
            )
            return None
        user_defaults = {
            "name": clean_user_info["name"],
            "email": clean_user_info["email"],
            "is_active": not clean_user_info["deleted"],
            "first_name": clean_user_info["first_name"],
            "last_name": clean_user_info["last_name"],
            "avatar": clean_user_info["image"],
        }
        if user_info.get("is_bot") is True:
            user_defaults["bot"] = True
        username = clean_user_info["email"].split("@")[0]
        try:
            user, _ = User.objects.update_or_create(
                username=username,
                defaults=user_defaults,
            )
        except IntegrityError:
            logger.warning(
                f"User with username {username} already exists. Trying with email instead"
            )
            user_defaults = user_defaults.pop("email", None)
            user, _ = User.objects.update_or_create(
                email=clean_user_info["email"],
                defaults=user_defaults,
            )

        if not user:
            logger.error(
                "Could not upsert user in DB, after trying to match with username then email"
            )
            return None

        # TODO Handle case of user but with outdated email
        logger.debug("Creating Slack user")
        logger.debug(user_info)
        slack_user, _ = self.get_or_create_from_slack(user_info=user_info, user=user)
        if not slack_user:
            logger.error("Could not upsert slack_user in DB WTF")
            return None

        return user

    @staticmethod
    def unpack_user_info(user_info: SlackResponse | dict[str, Any]) -> dict[str, Any]:
        """Returns a dict contains fields for the SlackUser, from a SlackResponse.
        email, name and id should always be returned.
        """
        user_args = {}
        if user_info.get("user") and user_info["user"] is not None:
            user_info = cast("dict[str, Any]", user_info["user"])

        user_args["slack_id"] = get_in(user_info, "id")
        user_args["first_name"] = get_in(user_info, "profile.first_name")
        user_args["last_name"] = get_in(user_info, "profile.last_name")
        user_args["deleted"] = get_in(user_info, "deleted")

        # TODO Fix mess with name vs username
        username = get_in(user_info, "name")
        if username:
            user_args["username"] = username

        if not get_in(user_info, "is_bot") and get_in(user_info, "id") != "USLACKBOT":
            user_args["email"] = get_in(user_info, "profile.email")
            user_args["name"] = get_in(user_info, "profile.real_name")
        else:
            user_args["email"] = get_in(user_info, "name")
            user_args["name"] = get_in(user_info, "profile.real_name")

        if get_in(user_info, "profile.image_512"):
            avatar = get_in(user_info, "profile.image_512")
            if avatar and len(
                avatar
            ):  # <= SlackUser._meta.get_field('image').max_length:
                user_args["image"] = avatar
        elif get_in(user_info, "profile.image_192"):
            avatar = get_in(user_info, "profile.image_192")
            if avatar and len(
                avatar
            ):  # <= SlackUser._meta.get_field('image').max_length:
                user_args["image"] = avatar

        if user_args["first_name"] is None:
            user_args["first_name"] = user_args["name"].split(" ")[0]
        if user_args["last_name"] is None:
            user_args["last_name"] = user_args["name"].split(" ")[-1]
        return user_args


class SlackUser(models.Model):
    """Holds data about a Slack User, linked to an :model:`incidents.user`.
    slack_id field is not used as PK, as it is only guaranteed by Slack to be unique in pair with a team_id.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slack_id = models.CharField(max_length=32, unique=True)
    user = models.OneToOneField[User, User](
        "incidents.User", on_delete=models.CASCADE, related_name="slack_user"
    )

    # Optional fields, for display
    username = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="The Slack handle of a Slack user (@handle)",
    )
    image = models.URLField(null=True, blank=True)

    class Meta(TypedModelMeta):
        indexes = [
            models.Index(fields=["slack_id"]),
        ]

    def __str__(self) -> str:
        return self.slack_id

    def get_absolute_url(self) -> str:
        return self.url

    @property
    def link(self) -> str:
        return f"slack://user?team={SlackApp().details['team_id']}&id={self.slack_id}"

    @property
    def url(self) -> str:
        """Returns an HTTPS ULR to the Slack user's profile. For deep linking, use `link` instead."""
        return urljoin(SlackApp().details["url"], f"team/{self.slack_id}")

    @slack_client
    def update_user_info(
        self,
        client: WebClient = DefaultWebClient,
    ) -> None:
        try:
            user_info = client.users_info(user=self.slack_id)
            if not user_info.get("ok"):
                logger.warning("Could not fetch user from firefighter.slack.")
                return
        except slack_sdk.errors.SlackApiError:
            logger.exception(f"Could not find Slack user with ID: {self.slack_id}")
            return
        clean_user_info = SlackUser.objects.unpack_user_info(user_info=user_info)

        if clean_user_info.get("slack_id"):
            clean_user_info.pop("slack_id", None)

        # Remove the email, not wanted in the defaults (no email field on SlackUser)
        # TODO Remove all dict keys that are not fields of the SlackUser
        # TODO Refactor when users are already saved
        email = clean_user_info.pop("email", None)
        name = clean_user_info.pop("name", None)
        first_name = clean_user_info.pop("first_name", None)
        last_name = clean_user_info.pop("last_name", None)
        deleted = clean_user_info.pop("deleted", None)
        if name:
            User.objects.filter(slack_user__slack_id=self.slack_id).update(name=name)
        if first_name:
            User.objects.filter(slack_user__slack_id=self.slack_id).update(
                first_name=first_name
            )
        if last_name:
            User.objects.filter(slack_user__slack_id=self.slack_id).update(
                last_name=last_name
            )
        if deleted is not None:
            User.objects.filter(slack_user__slack_id=self.slack_id).update(
                is_active=(not deleted)
            )
        logger.debug(clean_user_info)
        SlackUser.objects.filter(slack_id=self.slack_id).update(**clean_user_info)

        # Update the User (not SlackUser)
        if name or first_name or last_name or email or deleted is not None:
            user_kwargs = {}
            if name:
                user_kwargs["name"] = name
            if email:
                user_kwargs["email"] = email
            if first_name:
                user_kwargs["first_name"] = first_name
            if last_name:
                user_kwargs["last_name"] = last_name
            if deleted is not None:
                user_kwargs["is_active"] = not deleted
            user_kwargs["updated_at"] = timezone.now()
            User.objects.filter(slack_user__slack_id=self.slack_id).update(
                **user_kwargs
            )

    @slack_client
    def send_private_message(
        self,
        message: SlackMessageSurface,
        client: WebClient = DefaultWebClient,
        **kwargs: Any,
    ) -> None:
        """Send a private message to the user."""
        client.chat_postMessage(
            channel=self.slack_id,
            text=message.get_text(),
            metadata=message.get_metadata(),
            blocks=message.get_blocks(),
            **kwargs,
        )

    objects: SlackUserManager = SlackUserManager()
