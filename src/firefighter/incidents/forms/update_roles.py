from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.forms import Field

    from firefighter.incidents.models.incident import Incident


class IncidentUpdateRolesForm(forms.Form):
    incident: Incident
    user: User | None
    initial: dict[str, Any]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.incident: Incident = kwargs.pop("incident")
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.generate_fields_dynamically()

    def generate_fields_dynamically(self) -> None:
        roles_types_base = IncidentRoleType.objects.order_by("order")
        self.incident_roles = self.get_incident_roles(roles_types_base)

        for incident_role in self.incident_roles:
            field_name = f"role_{incident_role.role_type.slug}"
            self.fields[field_name] = forms.ModelChoiceField(
                queryset=User.objects.all(),
                required=incident_role.role_type.required,
                label=incident_role.role_type.name,
                help_text=(
                    f"{incident_role.role_type.emoji} "
                    if incident_role.role_type.emoji
                    else ""
                )
                + incident_role.role_type.summary,
                initial=incident_role.user if hasattr(incident_role, "user") else None,
            )

            logger.debug(
                f"Initial {field_name} was set to {self.initial.get(field_name)}"
            )

    def clean(self) -> dict[str, Any] | None:
        if self.user is None:
            raise forms.ValidationError("User is required")
        # XXX Validate that we have all fields and no extra fields
        return super().clean()

    def save(self) -> None:
        """Custom save method to save the updated roles."""
        self.fields: dict[str, Field]
        roles_to_update: dict[str, User | None] = {}
        for field_name in self.fields:
            if field_name not in self.changed_data or self.fields[field_name].disabled:
                logger.debug("skipping %s", field_name)
                continue
            if not field_name.startswith("role_"):
                continue

            role_type_slug = field_name.replace("role_", "")

            roles_to_update[role_type_slug] = self.cleaned_data[field_name]
        if self.user is None:
            raise RuntimeError("User is required, was the form validated?")
        self.incident.update_roles(self.user, roles_to_update)

    def get_incident_roles(
        self,
        incident_role_types: Iterable[IncidentRoleType],
    ) -> list[IncidentRole]:
        incident_roles: list[IncidentRole] = []
        for incident_role_type in incident_role_types:
            # Get the IncidentRole if it exists in DB, or create it locally with User=None
            try:
                incident_role = IncidentRole.objects.get(
                    incident=self.incident, role_type=incident_role_type
                )
            except IncidentRole.DoesNotExist:
                incident_role = IncidentRole(
                    incident=self.incident, role_type=incident_role_type, user=None
                )
            incident_roles.append(incident_role)
        return incident_roles
