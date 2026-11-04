"""Origin fields (internal / partner), shared by every form that records the origin.

The fields are added from `__init__` rather than declared, so that they come last in
each form and take the form's own field prefix (the Key Events message prefixes all
its fields).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import forms

from firefighter.incidents.enums import IncidentOrigin
from firefighter.incidents.forms.utils import EnumChoiceField
from firefighter.incidents.models.partner import Partner
from firefighter.incidents.origin import apply_origin, resolve_partner

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

ORIGIN_FIELD = "origin"
PARTNER_FIELD = "partner"
NEW_PARTNER_FIELD = "new_partner"


class OriginFieldsMixin(forms.Form):
    """Adds, validates and saves the origin fields of a Django form.

    Declares no field itself, so it does not change the order of the form's fields.
    """

    origin_prefix: str = ""
    """Prefixed to the origin field names (the form's own field prefix)."""
    origin_allows_new_partner: bool = True
    """Offer "Partner not in the list? Add it". Slack only accepts a text input in a
    modal, not in a message such as the Key Events one."""
    origin_requires_partner: bool = True
    """Whether origin Partner needs a partner to validate. The Key Events message saves
    on every change, so it lets the origin be set before the partner."""

    def add_origin_fields(self, incident: Incident | None) -> None:
        """Append the origin fields, initialised from `incident`."""
        # Not required: a form without it (e.g. a Key Events message posted before the
        # origin existed) leaves the origin unchanged. Slack always submits the select,
        # which has an initial value.
        self.fields[self.origin_prefix + ORIGIN_FIELD] = EnumChoiceField(
            enum_class=IncidentOrigin,
            required=False,
            empty_value=None,
            label="Origin of the incident",
            help_text="Partner: the incident comes from a third party we depend on (search, CDN, payment...).",
            initial=IncidentOrigin(incident.origin)
            if incident
            else IncidentOrigin.INTERNAL,
        )
        active_partners = Partner.objects.filter(is_active=True).order_by("name")
        # Slack refuses a select without options: no list until a partner exists
        if active_partners.exists():
            self.fields[self.origin_prefix + PARTNER_FIELD] = forms.ModelChoiceField(
                queryset=active_partners,
                required=False,
                label="Partner",
                initial=incident.partner if incident else None,
            )
        if self.origin_allows_new_partner:
            self.fields[self.origin_prefix + NEW_PARTNER_FIELD] = forms.CharField(
                required=False,
                max_length=128,
                label="Partner not in the list? Add it",
            )

    def _origin_values(self) -> tuple[Any, Partner | None, str]:
        data = self.cleaned_data
        return (
            data.get(self.origin_prefix + ORIGIN_FIELD),
            data.get(self.origin_prefix + PARTNER_FIELD),
            (data.get(self.origin_prefix + NEW_PARTNER_FIELD) or "").strip(),
        )

    def clean_origin_fields(self) -> None:
        """Origin Partner needs a partner, picked or typed. Call from the form's `clean()`."""
        if not self.origin_requires_partner:
            return
        origin, partner, new_partner = self._origin_values()
        if origin == IncidentOrigin.PARTNER and partner is None and not new_partner:
            partner_field = self.origin_prefix + PARTNER_FIELD
            self.add_error(
                partner_field
                if partner_field in self.fields
                else self.origin_prefix + NEW_PARTNER_FIELD,
                "Pick the partner, or add it if it is not in the list.",
            )

    def save_origin_fields(self, incident: Incident, user: User | None) -> bool:
        """Apply the submitted origin to the incident. Returns whether it changed."""
        origin, partner, new_partner = self._origin_values()
        if not origin:
            return False
        if origin == IncidentOrigin.PARTNER:
            partner = resolve_partner(
                partner, new_partner, user=user, incident=incident
            )
        return apply_origin(incident, origin, partner, user=user)


def origin_initial(incident: Incident) -> dict[str, Any]:
    """Initial values of the origin fields, to merge into a form's `initial`."""
    return {
        ORIGIN_FIELD: IncidentOrigin(incident.origin),
        PARTNER_FIELD: incident.partner,
    }
