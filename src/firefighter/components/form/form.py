from __future__ import annotations

import logging
from typing import Any, NotRequired, TypedDict

from django import forms
from django_components import component
from django_components.slots import SlotContent

logger = logging.getLogger(__name__)


class Slots(TypedDict, total=False):
    form_footer: NotRequired[SlotContent[Any]]


class Data(TypedDict):
    form: forms.Form


@component.register("form")
class FormComponent(component.Component):
    template_name = "form/form.html"

    def get_context_data(self, form: forms.Form, **kwargs: Any) -> Data:
        return Data(form=form)
