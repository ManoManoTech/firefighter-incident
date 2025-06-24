from __future__ import annotations

import logging
from typing import Any, NotRequired, Required, TypedDict, Unpack

from django.utils.safestring import SafeString
from django_components import component
from django_components.slots import SlotFunc

logger = logging.getLogger(__name__)

SlotContent = str | SafeString | SlotFunc[Any]


class Kwargs(TypedDict, total=False):
    autoplay: Required[bool]
    header: NotRequired[bool]


class Data(TypedDict):
    autoplay: bool


class Slots(TypedDict):
    modal_header: NotRequired[SlotContent]
    modal_content: NotRequired[SlotContent]
    modal_enabler: NotRequired[SlotContent]


@component.register("modal")
class Modal(component.Component):
    template_name = "modal/modal.html"

    def get_context_data(self, *args: Any, **kwargs: Unpack[Kwargs]) -> Data:
        return Kwargs(autoplay=kwargs["autoplay"])
