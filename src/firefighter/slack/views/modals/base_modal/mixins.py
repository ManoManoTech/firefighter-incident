from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from firefighter.slack.slack_app import SlackApp
from firefighter.slack.views.modals.base_modal.base import SlackModal
from firefighter.slack.views.modals.base_modal.base_mixins import (
    IncidentSelectableModalMixinBase,
)
from firefighter.slack.views.modals.select import modal_select

if TYPE_CHECKING:
    from re import Pattern

    from slack_sdk.models.views import View

app = SlackApp()

logger = logging.getLogger(__name__)


class IncidentSelectableModalMixin(IncidentSelectableModalMixinBase):
    callback_id: str | Pattern[str]
    select_modal_title: str = "Select an incident"
    select_incident_title: str = "Select a critical incident"

    def build_modal_with_context(self, body: dict[str, Any], **kwargs: Any) -> View:
        # XXX Should use a Protocol for typings
        if not isinstance(self, SlackModal):
            err_msg = (
                f"{self.__class__.__name__} must be a subclass of {SlackModal.__name__}"
            )
            raise TypeError(err_msg)
        self._get_kwargs_builder(body, kwargs, self.builder_fn_args)
        if "body" in self.builder_fn_args:
            kwargs["body"] = body
        elif "body" in kwargs:
            del kwargs["body"]

        if "incident" in self.builder_fn_args and kwargs.get("incident") is None:
            if kwargs.get("callback_id") is None:
                kwargs["callback_id"] = self.callback_id
            kwargs.pop("body", None)
            return modal_select.build_modal_fn(**kwargs, select_class=self)

        return self.build_modal_fn(**kwargs)  # type: ignore

    def get_callback_id(self) -> str | Pattern[str]:
        return self.callback_id

    def get_select_modal_title(self) -> str:
        return self.select_modal_title

    def get_select_title(self) -> str:
        return self.select_incident_title
