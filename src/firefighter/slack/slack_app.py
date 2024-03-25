from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ParamSpec, Self, TypedDict, TypeVar

from django.conf import settings
from slack_bolt.app.app import App
from slack_bolt.middleware.authorization.single_team_authorization import (
    SingleTeamAuthorization,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from slack_sdk.web.client import WebClient

logger = logging.getLogger(__name__)


class SlackAppDetails(TypedDict):
    url: str
    team_id: str
    team: str
    user: str
    user_id: str
    bot_id: str
    is_enterprise_install: bool


class SlackApp(App):
    """Subclass of the Slack App, as a singleton."""

    instance: App | None = None
    details: SlackAppDetails

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if not cls.instance:
            if settings.FF_SLACK_SKIP_CHECKS:
                logger.warning(
                    "Skipping Slack checks! Only use for testing or demo. Features related to the Bot User or the Workspace may not work (e.g. some generated URLs may be invalid)"
                )
                kwargs["token_verification_enabled"] = False
                kwargs["request_verification_enabled"] = False
                kwargs["ssl_check_enabled"] = False
                kwargs["url_verification_enabled"] = False

            slack_bot_token: str = settings.SLACK_BOT_TOKEN
            slack_signing_secret: str = settings.SLACK_SIGNING_SECRET
            kwargs["token"] = slack_bot_token
            kwargs["signing_secret"] = slack_signing_secret
            kwargs["ignoring_self_events_enabled"] = False
            cls.instance = App(*args, **kwargs)
            single_team_authorization = next(
                filter(
                    lambda m: isinstance(m, SingleTeamAuthorization),
                    cls.instance._middleware_list,  # noqa: SLF001
                )
            )

            if isinstance(single_team_authorization, SingleTeamAuthorization):
                res = single_team_authorization.auth_test_result
                if settings.FF_SLACK_SKIP_CHECKS:
                    cls.details = cls.instance.details = SlackAppDetails(  # type: ignore
                        url="",
                        team="",
                        user="",
                        team_id="",
                        user_id="",
                        bot_id="",
                        is_enterprise_install=False,
                    )
                    return cls.instance  # type: ignore[return-value]
                if res is None:
                    logger.critical("Could not verify Slack credentials! Exiting.")
                    raise RuntimeError("Could not verify Slack credentials! Exiting.")
                if not res.get("ok"):
                    logger.critical(
                        "Could not verify Slack credentials! Exiting. Credentials: %s",
                        res,
                    )
                    raise RuntimeError("Could not verify Slack credentials! Exiting.")
                cls.details = cls.instance.details = SlackAppDetails(  # type: ignore
                    url=res["url"],
                    team=res["team"],
                    user=res["user"],
                    team_id=res["team_id"],
                    user_id=res["user_id"],
                    bot_id=res["bot_id"],
                    is_enterprise_install=res["is_enterprise_install"],
                )
                logger.debug("SlackAppDetails: %s", cls.details)
        return cls.instance  # type: ignore[return-value]


P = ParamSpec("P")
R = TypeVar("R")


# Now we can type the decorator more accurately
def slack_client(function: Callable[P, R]) -> Callable[P, R]:
    """Adds a Slack client in `client` kwargs, if none is provided.

    Can be used as a decorator with `@slack_client` or as a function with `slack_client(function)`.
    """

    def wrap_function(*args: P.args, **kwargs: P.kwargs) -> R:
        if "client" not in kwargs:
            kwargs["client"] = SlackApp().client
        return function(*args, **kwargs)

    return wrap_function


DefaultWebClient: WebClient = None  # type: ignore
