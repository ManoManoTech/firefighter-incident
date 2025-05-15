from __future__ import annotations

import inspect
import logging
import operator
import re
from functools import reduce
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from django.forms import Form
from slack_bolt.request.payload_utils import (
    to_command,
    to_event,
    to_message,
    to_options,
    to_shortcut,
    to_step,
    to_view,
)

from firefighter.slack.models.user import SlackUser
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.slack_incident_context import (
    get_incident_from_context,
    get_user_from_context,
)
from firefighter.slack.utils import get_slack_user_id_from_body, respond
from firefighter.slack.views.modals.base_modal.form_utils import (
    SlackForm,
    slack_view_submission_to_dict,
)
from firefighter.slack.views.modals.base_modal.modal_utils import (
    open_modal,
    push_modal,
    update_modal,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.core.exceptions import ValidationError
    from slack_bolt.context.ack.ack import Ack
    from slack_bolt.request.request import BoltRequest
    from slack_bolt.response.response import BoltResponse
    from slack_sdk.models.blocks.blocks import Block
    from slack_sdk.models.views import View

T = TypeVar("T", bound=Form)
app = SlackApp()

logger = logging.getLogger(__name__)


class SlackModal:
    """Two main responsibilities:
    - Register the modal on Slack to open it with shortcuts or actions
    - Provide useful context for `build_modal_fn` and `handle_modal_fn`, such as body, incident, user, etc.
    """

    callback_id: str | re.Pattern[str]
    """Callback ID for the Slack View"""

    open_shortcut: str | None = None
    """[Slack shortcut](https://api.slack.com/interactivity/shortcuts) to open the modal."""

    open_action: str | list[str] | None = None
    update_action: str | list[str] | None = None
    push_action: str | list[str] | None = None

    build_modal_fn: Callable[..., View | list[Block]]
    handle_modal_fn: Callable[[Any], Any] | None

    def __init__(self) -> None:
        if self.handle_modal_fn is not None:
            self.handler_fn_args = inspect.getfullargspec(self.handle_modal_fn).args
            if len(self.handler_fn_args) > 0 and self.handler_fn_args[0] in {
                "self",
                "cls",
            }:
                self.handler_fn_args.pop(0)

        self.builder_fn_args = inspect.getfullargspec(self.build_modal_fn).args
        if len(self.builder_fn_args) > 0 and self.builder_fn_args[0] in {"self", "cls"}:
            self.builder_fn_args.pop(0)

        self._register_actions_shortcuts()

    def open_modal_aio(self, ack: Ack, body: dict[str, Any], **kwargs: Any) -> None:
        ack()

        view = self.build_modal_with_context(body, **kwargs)

        open_modal(view=view, body=body)

    def build_modal_with_context(self, body: dict[str, Any], **kwargs: Any) -> View:
        self._get_kwargs_builder(body, kwargs, self.builder_fn_args)
        if "body" in self.builder_fn_args:
            kwargs["body"] = body
        elif "body" in kwargs:
            del kwargs["body"]

        return self.build_modal_fn(**kwargs)  # type: ignore[return-value]

    def _register_actions_shortcuts(self) -> None:
        """Register the different actions and shortcuts, from the class attributes."""
        self._register_meta(
            app.action, self.open_action, self._handle_shortcut_action_open
        )
        self._register_meta(app.action, self.update_action, self._handle_action_update)
        self._register_meta(app.action, self.push_action, self._handle_action_push)
        self._register_meta(
            app.shortcut, self.open_shortcut, self._handle_shortcut_action_open
        )

        target = app.action if hasattr(self, "callback_action") else app.view
        self._register_meta(target, self.callback_id, self._handle_modal)

    def _handle_shortcut_action(
        self, request: BoltRequest, response: BoltResponse, **kwargs: Any
    ) -> tuple[View, dict[str, Any]]:
        fn_kwargs, body = self._get_handler_kwargs(
            request, response, self.builder_fn_args
        )
        if "body" not in fn_kwargs:
            fn_kwargs["body"] = body

        request.context.ack()
        return self.build_modal_with_context(**fn_kwargs), body

    def _handle_shortcut_action_open(
        self, request: BoltRequest, response: BoltResponse, **kwargs: Any
    ) -> None:
        view, body = self._handle_shortcut_action(request, response, **kwargs)
        open_modal(view=view, body=body)

    def _handle_action_update(
        self, request: BoltRequest, response: BoltResponse, **kwargs: Any
    ) -> None:
        view, body = self._handle_shortcut_action(request, response, **kwargs)
        update_modal(view=view, body=body)

    def _handle_action_push(
        self, request: BoltRequest, response: BoltResponse, *args: Any, **kwargs: Any
    ) -> None:
        view, body = self._handle_shortcut_action(request, response, **kwargs)
        push_modal(view=view, body=body)

    def _handle_modal(
        self, request: BoltRequest, response: BoltResponse, **kwargs: Any
    ) -> None:
        """Wrapper to add the required args to the handle_modal_fn."""
        if self.handle_modal_fn is None:
            raise ValueError("No handle_modal_fn defined!")

        fn_kwargs, body = self._get_handler_kwargs(
            request, response, self.handler_fn_args
        )

        if "incident" in self.handler_fn_args and fn_kwargs["incident"] is None:
            logger.error(f"Could not get the incident from slack context! Body: {body}")
            respond(
                body=body,
                text="Unexpected error when fetching this incident. Please tell @pulse (#tech-pe-pulse) about the context of this error.",
            )
            return
        if "user" in self.handler_fn_args and fn_kwargs["user"] is None:
            logger.error(f"Could not get the user from slack context! Body: {body}")
            respond(
                body=body,
                text="Unexpected error when fetching your user. Please tell @pulse (#tech-pe-pulse) about the context of this error.",
            )
            return

        self.handle_modal_fn(**fn_kwargs)  # type: ignore

    @staticmethod
    def _get_kwargs_builder(
        body: dict[str, Any], kwargs: dict[str, Any], args: list[str]
    ) -> None:
        """Adds `user` and `incident` to the kwargs from the body context, if they are needed and not present."""
        if "incident" in args and kwargs.get("incident") is None:
            kwargs["incident"] = get_incident_from_context(body)

        if "user" in args and kwargs.get("user") is None:
            sender_id = get_slack_user_id_from_body(body)
            if sender_id:
                kwargs["user"] = SlackUser.objects.get_user_by_slack_id(
                    slack_id=sender_id
                )
            else:
                logger.warning(
                    f"Could not get the user from slack context! Body: {body}"
                )
                kwargs["user"] = None

    @staticmethod
    def _get_handler_kwargs(
        request: BoltRequest, response: BoltResponse, args: list[str]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Adapted from Slack Bolt. Provide the kwargs for the function, from the Slack request and response.
        Additionally, it can provide the incident and user from the Slack context.

        Args:
            request (BoltRequest): The Slack request
            response (BoltResponse): The Slack response
            args (list[str]): List of args of the function

        Returns:
            tuple[dict[str, Any], dict[str, Any]]: kwargs for the function, body of the response
        """
        all_available_args = {
            "logger": logger,
            "client": request.context.client,
            "req": request,
            "request": request,
            "resp": response,
            "response": response,
            "context": request.context,
            # payload
            "body": request.body,
            "options": to_options(request.body),
            "shortcut": to_shortcut(request.body),
            "view": to_view(request.body),
            "command": to_command(request.body),
            "event": to_event(request.body),
            "message": to_message(request.body),
            "step": to_step(request.body),
            # utilities
            "ack": request.context.ack,
            "say": request.context.say,
            "respond": request.context.respond,
            # middleware
        }

        # Add Slack Bolt Context
        fn_kwargs: dict[str, Any] = {
            k: v for k, v in all_available_args.items() if k in args
        }
        body: dict[str, Any] = all_available_args["body"]  # type: ignore

        # Add custom context if needed
        if "incident" in args:
            fn_kwargs["incident"] = get_incident_from_context(body)

        if "user" in args:
            fn_kwargs["user"] = get_user_from_context(body)

        return fn_kwargs, body

    @staticmethod
    def _register_meta(
        fn_register: Callable[
            [str | re.Pattern[str]], Callable[[Callable[..., Any]], Any]
        ],
        attributes: list[str] | str | re.Pattern[str] | None,
        fn: Callable[..., Any] | None,
    ) -> None:
        if fn is None:
            logger.debug(
                f"Skipping registration {fn_register.__name__} with {attributes}"
            )
            return
        if attributes is not None:
            if isinstance(attributes, str | re.Pattern):
                fn_register(attributes)(fn)
            else:
                for action in attributes:
                    fn_register(action)(fn)


class ModalForm(SlackModal, Generic[T]):
    """Specific SlackModal to handle a Django form.

    Provided a Django form in form_class, it will handle:
    - generation of Slack Blocks
    - validation and submission of the form
    """

    form_class: type[T] | None
    form: T

    def get_form_class(self) -> SlackForm[T]:
        if self.form_class is None:
            raise ValueError("No form_class defined!")
        return SlackForm(self.form_class)

    def handle_form_errors(
        self,
        ack: Ack,
        body: dict[str, Any],
        forms_kwargs: dict[str, Any],
        *,
        ack_on_success: bool = True,
    ) -> SlackForm[T] | None:
        slack_form = self.get_form_class()(
            data=slack_view_submission_to_dict(body), **forms_kwargs
        )
        form = slack_form.form
        if form.is_valid():
            if ack_on_success:
                ack()
        else:
            ack(
                response_action="errors",
                errors={
                    k: self._concat_validation_errors_msg(v)
                    for k, v in form.errors.as_data().items()
                },
            )
            return None
        return slack_form

    @staticmethod
    def _concat_validation_errors_msg(err: list[ValidationError]) -> str:
        """Return a string of all validation errors."""
        return reduce(operator.add, ["; ".join(e.messages) for e in err], "")


class MessageForm(SlackModal, Generic[T]):
    """Form wrapper to use a Django form in a Slack message.

    Provided a Django form in form_class, it will handle:
    - generation of Slack Blocks
    - validation and submission of the form
    """

    form_class: type[T] | None
    form: T

    def get_form_class(self) -> SlackForm[T]:
        if self.form_class is None:
            raise ValueError("No form_class defined!")
        return SlackForm(self.form_class, {})

    def handle_form_errors(
        self, ack: Ack, body: dict[str, Any], forms_kwargs: dict[str, Any]
    ) -> SlackForm[T] | None:
        slack_form = self.get_form_class()(
            data=slack_view_submission_to_dict(body), **forms_kwargs
        )
        form = slack_form.form
        # Only change one field, so only one data. We add the rest from the initial data.
        form.data = {**form.initial, **form.data}
        if form.is_valid():
            ack(text="Updated successfully!", response_type="ephemeral")
        else:
            logger.warning("Form errors in Slack context.")
            logger.warning(form.errors.as_data())

            ack(text="Error", response_type="ephemeral")

        return slack_form
