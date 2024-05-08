from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.blocks import ContextBlock

from firefighter.raid.forms import (
    CreateNormalCustomerIncidentForm,
    CreateRaidDocumentationRequestIncidentForm,
    CreateRaidFeatureRequestIncidentForm,
    CreateRaidInternalIncidentForm,
    RaidCreateIncidentSellerForm,
)
from firefighter.slack.views.modals.opening.set_details import SetIncidentDetails

if TYPE_CHECKING:
    from firefighter.slack.views.modals.base_modal.form_utils import (
        SlackFormAttributesDict,
    )

logger = logging.getLogger(__name__)

slack_fields: SlackFormAttributesDict = {
    "title": {
        "input": {
            "multiline": False,
            "placeholder": "Summary of the issue.",
        },
        "block": {"hint": None},
    },
    "description": {
        "input": {
            "multiline": True,
            "placeholder": "Explain your issue in English giving as much details as possible. It helps people handling the issue. \nThis description can be edited later.",
        },
        "block": {"hint": None},
    },
    "suggested_team_routing": {
        "widget": {
            "post_block": ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text="Feature Team or Train that should own the issue. If you don't know access <https://manomano.atlassian.net/wiki/spaces/QRAFT/pages/3970335291/Teams+and+owners|here> for guidance."
                    ),
                ]
            )
        },
    },
    "area": {
        "input": {
            "placeholder": "Select affected area",
        },
    },
}


class CreateRaidCustomerIncidentFormSlack(CreateNormalCustomerIncidentForm):
    slack_fields: SlackFormAttributesDict = slack_fields


class OpeningRaidCustomerModal(SetIncidentDetails[CreateRaidCustomerIncidentFormSlack]):
    open_action: str = "open_incident_raid_customer_request"
    push_action: str = "push_raid_customer_request"
    callback_id: str = "open_incident_raid_customer_request"
    id = "raid_customer_request"
    title = "New Customer Incident"

    form_class = CreateRaidCustomerIncidentFormSlack


class CreateRaidDocumentationRequestIncidentFormSlack(
    CreateRaidDocumentationRequestIncidentForm
):
    slack_fields: SlackFormAttributesDict = slack_fields


class CreateRaidFeatureRequestIncidentFormSlack(CreateRaidFeatureRequestIncidentForm):
    slack_fields: SlackFormAttributesDict = slack_fields


class OpeningRaidFeatureRequestModal(
    SetIncidentDetails[CreateRaidFeatureRequestIncidentFormSlack]
):
    open_action: str = "open_incident_raid_feature_request"
    push_action: str = "push_raid_feature_request"
    callback_id: str = "open_incident_raid_feature_request"

    title = "New Feature Request"
    form_class = CreateRaidFeatureRequestIncidentFormSlack


class OpeningRaidDocumentationRequestModal(
    SetIncidentDetails[CreateRaidDocumentationRequestIncidentFormSlack]
):
    open_action: str = "open_incident_raid_documentation_request"
    push_action: str = "push_raid_documentation_request"
    callback_id: str = "open_incident_raid_documentation_request"

    title = "New Documentation Request"
    form_class = CreateRaidDocumentationRequestIncidentFormSlack


class CreateRaidInternalIncidentFormSlack(CreateRaidInternalIncidentForm):
    slack_fields: SlackFormAttributesDict = slack_fields


class OpeningRaidInternalModal(SetIncidentDetails[CreateRaidInternalIncidentFormSlack]):
    open_action: str = "open_incident_raid_internal_request"
    push_action: str = "push_raid_internal_request"
    callback_id: str = "open_incident_raid_internal_request"

    title = "New Internal Incident"

    form_class = CreateRaidInternalIncidentFormSlack


class CreateRaidSellerIncidentFormSlack(RaidCreateIncidentSellerForm):
    slack_fields: SlackFormAttributesDict = slack_fields


class OpeningRaidSellerModal(SetIncidentDetails[CreateRaidSellerIncidentFormSlack]):
    open_action: str = "open_incident_raid_seller_request"
    push_action: str = "push_raid_seller_request"
    callback_id: str = "open_incident_raid_seller_request"

    title = "New Seller Incident"
    form_class = CreateRaidSellerIncidentFormSlack


# Instantiate all the modals to register actions
_modals = [
    raid_seller := OpeningRaidSellerModal(),
    raid_internal := OpeningRaidInternalModal(),
    raid_customer := OpeningRaidCustomerModal(),
    raid_feature := OpeningRaidFeatureRequestModal(),
    raid_documentation := OpeningRaidDocumentationRequestModal(),
]
