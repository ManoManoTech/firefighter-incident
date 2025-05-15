from __future__ import annotations

import logging
from typing import Any, TypedDict

from django.contrib.messages.storage.base import BaseStorage
from django_components import EmptyTuple, component

logger = logging.getLogger(__name__)


class Data(TypedDict):
    messages: BaseStorage


@component.register("messages")
class Messages(component.Component[EmptyTuple, Data, Data, Any]):  # type: ignore[type-var]
    template_name = "messages/messages.html"

    def get_context_data(self, messages: BaseStorage, **kwargs: Any) -> Data:
        return Data(messages=messages)
