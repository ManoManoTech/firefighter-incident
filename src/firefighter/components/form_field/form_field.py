from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django_components import component

if TYPE_CHECKING:
    from django import forms

logger = logging.getLogger(__name__)


@component.register("form_field")
class FormField(component.Component):
    template_name = "form_field/form_field.html"

    def get_context_data(
        self, field: forms.BoundField | forms.Field, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        if field is None:
            raise ValueError("Field not set!")

        input_class = "input-ff"

        return {"field": field, "field_input_class": input_class}
