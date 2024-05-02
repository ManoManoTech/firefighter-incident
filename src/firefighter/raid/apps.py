from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RaidConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "raid"
    name = "firefighter.raid"
    verbose_name = "RAID"

    def ready(self) -> None:
        import firefighter.raid.tasks
        import firefighter.raid.urls
        from firefighter.raid.signals import (
            incident_created,
            incident_updated,
        )
        from firefighter.raid.views.open_normal import (
            OpeningRaidCustomerModal,
            OpeningRaidDocumentationRequestModal,
            OpeningRaidFeatureRequestModal,
            OpeningRaidInternalModal,
            OpeningRaidSellerModal,
        )
        from firefighter.slack.views.modals.open import INCIDENT_TYPES

        INCIDENT_TYPES["normal"] = {
            "CUSTOMER": {
                "label": "Customer",
                "slack_form": OpeningRaidCustomerModal,
            },
            "SELLER": {
                "label": "Seller",
                "slack_form": OpeningRaidSellerModal,
            },
            "INTERNAL": {
                "label": "Internal",
                "slack_form": OpeningRaidInternalModal,
            },
            "DOCUMENTATION_REQUEST": {
                "label": "Documentation request",
                "slack_form": OpeningRaidDocumentationRequestModal,
            },
            "FEATURE_REQUEST": {
                "label": "Feature request",
                "slack_form": OpeningRaidFeatureRequestModal,
            },
        }

        return super().ready()
