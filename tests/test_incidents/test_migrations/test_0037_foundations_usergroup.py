"""Migration tests for `0037_link_foundations_slack_usergroup`.

`0036` leaves `Foundations` paging through the usergroups of the three
categories it supersedes. `0037` adds the consolidated usergroup on top,
without removing those — so a failure here degrades to "pages the old groups"
rather than "pages nobody".
"""

from __future__ import annotations

import pytest

MIGRATE_FROM = ("incidents", "0036_add_foundations_incident_category")
MIGRATE_TO = ("incidents", "0037_link_foundations_slack_usergroup")

USERGROUP_ID = "S0BL6GQPSQ3"


def _seed_foundations(old_state):
    """0036 only creates `Foundations` if the Marketplace group exists, and the
    test DB starts empty — so create both explicitly.
    """
    Group = old_state.apps.get_model("incidents", "Group")
    IncidentCategory = old_state.apps.get_model("incidents", "IncidentCategory")

    group, _ = Group.objects.get_or_create(name="Marketplace", defaults={"order": 1})
    category, _ = IncidentCategory.objects.get_or_create(
        name="Foundations", group=group, defaults={"order": 1, "enabled_create": True}
    )
    return category


@pytest.mark.django_db
class TestFoundationsUsergroupMigration:
    def test_creates_and_links_the_usergroup(self, migrator) -> None:
        old_state = migrator.apply_initial_migration(MIGRATE_FROM)
        _seed_foundations(old_state)

        new_state = migrator.apply_tested_migration(MIGRATE_TO)
        IncidentCategory = new_state.apps.get_model("incidents", "IncidentCategory")
        UserGroup = new_state.apps.get_model("slack", "UserGroup")

        foundations = IncidentCategory.objects.get(name="Foundations")
        usergroup = UserGroup.objects.get(usergroup_id=USERGROUP_ID)

        assert UserGroup.objects.filter(
            usergroup_id=USERGROUP_ID, incident_categories=foundations
        ).exists()
        # name/handle are placeholders; the Slack sync overwrites them by ID.
        assert usergroup.usergroup_id == USERGROUP_ID

    def test_reuses_an_existing_usergroup_row(self, migrator) -> None:
        """If the row already exists (created in admin), link it rather than
        duplicating — `usergroup_id` is the identity.
        """
        old_state = migrator.apply_initial_migration(MIGRATE_FROM)
        _seed_foundations(old_state)

        UserGroup = old_state.apps.get_model("slack", "UserGroup")
        UserGroup.objects.create(
            usergroup_id=USERGROUP_ID,
            name="created-by-hand",
            handle="created-by-hand",
        )

        new_state = migrator.apply_tested_migration(MIGRATE_TO)
        UserGroup = new_state.apps.get_model("slack", "UserGroup")

        assert UserGroup.objects.filter(usergroup_id=USERGROUP_ID).count() == 1

    def test_leaves_superseded_usergroups_linked(self, migrator) -> None:
        """Degrade-safe: the groups 0036 copied over stay attached."""
        old_state = migrator.apply_initial_migration(MIGRATE_FROM)
        category = _seed_foundations(old_state)

        UserGroup = old_state.apps.get_model("slack", "UserGroup")
        legacy = UserGroup.objects.create(
            usergroup_id="S08UV20CL6S",
            name="marketplace-mobile-apps",
            handle="marketplace-mobile-apps",
        )
        legacy.incident_categories.add(category)

        new_state = migrator.apply_tested_migration(MIGRATE_TO)
        UserGroup = new_state.apps.get_model("slack", "UserGroup")

        foundations = new_state.apps.get_model(
            "incidents", "IncidentCategory"
        ).objects.get(name="Foundations")

        assert UserGroup.objects.filter(
            usergroup_id="S08UV20CL6S", incident_categories=foundations
        ).exists()
        assert UserGroup.objects.filter(
            usergroup_id=USERGROUP_ID, incident_categories=foundations
        ).exists()
