"""Migration tests for `0036_add_foundations_incident_category`.

The Slack link copy is the load-bearing part of this migration: without it a
`Foundations` incident would page nobody, because
`firefighter.slack.signals.get_users` resolves responders through
`incident.incident_category.usergroups` / `.conversations`.
"""

from __future__ import annotations

import pytest

MIGRATE_FROM = ("incidents", "0035_incidentcategory_enabled_create")
MIGRATE_TO = ("incidents", "0036_add_foundations_incident_category")

RETIRED_NAMES = ["Mobile Apps", "Spartacux Foundations", "Web performance"]


def _seed_marketplace_categories(old_state):
    """Create the Marketplace group and the three categories being merged."""
    Group = old_state.apps.get_model("incidents", "Group")
    IncidentCategory = old_state.apps.get_model("incidents", "IncidentCategory")

    group = Group.objects.create(name="Marketplace", order=1)
    categories = {
        name: IncidentCategory.objects.create(
            name=name, group=group, order=order, enabled_create=True
        )
        for order, name in enumerate(RETIRED_NAMES, start=3)
    }
    return group, categories


@pytest.mark.django_db
class TestFoundationsMigration:
    def test_creates_foundations_and_retires_the_three(self, migrator) -> None:
        old_state = migrator.apply_initial_migration(MIGRATE_FROM)
        group, _ = _seed_marketplace_categories(old_state)

        new_state = migrator.apply_tested_migration(MIGRATE_TO)
        IncidentCategory = new_state.apps.get_model("incidents", "IncidentCategory")

        foundations = IncidentCategory.objects.get(name="Foundations")
        assert foundations.group_id == group.id
        # Takes the lowest order of the retired categories, so it lands in their place.
        assert foundations.order == 3
        assert foundations.enabled_create is True

        retired = IncidentCategory.objects.filter(name__in=RETIRED_NAMES)
        assert retired.count() == 3
        assert all(c.enabled_create is False for c in retired)

    def test_copies_slack_usergroups_and_conversations(self, migrator) -> None:
        """The step that makes `Foundations` actually page people."""
        old_state = migrator.apply_initial_migration(MIGRATE_FROM)
        _, categories = _seed_marketplace_categories(old_state)

        UserGroup = old_state.apps.get_model("slack", "UserGroup")
        Conversation = old_state.apps.get_model("slack", "Conversation")

        usergroup = UserGroup.objects.create(
            usergroup_id="S08UV20CL6S",
            name="marketplace-mobile-apps",
            handle="marketplace-mobile-apps",
        )
        usergroup.incident_categories.add(categories["Mobile Apps"])

        conversation = Conversation.objects.create(
            channel_id="C0001",
            name="impact-web-performance",
        )
        conversation.incident_categories.add(categories["Web performance"])

        new_state = migrator.apply_tested_migration(MIGRATE_TO)
        IncidentCategory = new_state.apps.get_model("incidents", "IncidentCategory")
        UserGroup = new_state.apps.get_model("slack", "UserGroup")
        Conversation = new_state.apps.get_model("slack", "Conversation")

        foundations = IncidentCategory.objects.get(name="Foundations")

        # Queried from the Slack side: historical models do not carry the
        # `related_name` accessors declared on the concrete models.
        assert UserGroup.objects.filter(
            name="marketplace-mobile-apps", incident_categories=foundations
        ).exists()
        assert Conversation.objects.filter(
            name="impact-web-performance", incident_categories=foundations
        ).exists()

        # The old categories keep their own links — nothing is moved away.
        assert UserGroup.objects.filter(
            name="marketplace-mobile-apps",
            incident_categories__name="Mobile Apps",
        ).exists()

    def test_does_not_touch_existing_incidents(self, migrator) -> None:
        """Non-destructive: incidents keep the category they were filed against."""
        old_state = migrator.apply_initial_migration(MIGRATE_FROM)
        _, categories = _seed_marketplace_categories(old_state)

        mobile_apps_id = categories["Mobile Apps"].id

        new_state = migrator.apply_tested_migration(MIGRATE_TO)
        IncidentCategory = new_state.apps.get_model("incidents", "IncidentCategory")

        # The row survives with the same primary key, so every FK pointing at it
        # (Incident.incident_category, IncidentUpdate.incident_category) is intact.
        assert IncidentCategory.objects.filter(id=mobile_apps_id).exists()
