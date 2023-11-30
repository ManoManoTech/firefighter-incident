from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django_components import component

if TYPE_CHECKING:
    from django import forms

logger = logging.getLogger(__name__)


@component.register("form")
class Form(component.Component):
    template_name = "form/form.html"

    def get_context_data(
        self, form: forms.Form, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        return {
            "form": form,
        }
