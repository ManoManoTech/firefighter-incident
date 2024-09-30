from __future__ import annotations

import logging
from typing import (
    Any,
    Never,
    TypedDict,
)

from django import forms
from django_components import EmptyTuple, component

logger = logging.getLogger(__name__)


class Data(TypedDict):
    field: forms.Field | forms.BoundField
    field_input_class: str


class Kwargs(TypedDict, total=True):
    field: forms.Field | forms.BoundField


@component.register("form_field")
class FormField(component.Component[EmptyTuple, Kwargs, Data, Any]):
    template_name = "form_field/form_field.html"

    def get_context_data(
        self, field: forms.BoundField | forms.Field, **kwargs: Never
    ) -> Data:
        input_class = "input-ff"

        return {"field": field, "field_input_class": input_class}
