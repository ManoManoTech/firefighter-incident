from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group

from firefighter.firefighter.sso import link_auth_user
from firefighter.incidents.factories import UserFactory


@pytest.mark.django_db
class TestLinkAuthUser:
    """Test cases for the link_auth_user function."""

    def test_link_auth_user_no_roles_claim(self) -> None:
        """Test that function returns early when no roles in claim."""
        user = UserFactory.create()
        claim = {"some_other_field": "value"}

        link_auth_user(user, claim)

        # No changes should be made
        assert list(user.groups.all()) == []

    def test_link_auth_user_roles_not_list(self) -> None:
        """Test that function returns early when roles is not a list."""
        user = UserFactory.create()
        claim = {"roles": "not_a_list"}

        link_auth_user(user, claim)

        # No changes should be made
        assert list(user.groups.all()) == []

    def test_link_auth_user_with_back_office_role(self) -> None:
        """Test that back_office role grants staff status."""
        user = UserFactory.create(is_staff=False)
        claim = {"roles": ["back_office", "other_role"]}

        # Create a group for testing
        Group.objects.create(name="other_role")

        link_auth_user(user, claim)

        user.refresh_from_db()
        assert user.is_staff is True
        # back_office should be removed from group assignment
        assert list(user.groups.values_list("name", flat=True)) == ["other_role"]

    def test_link_auth_user_back_office_already_staff(self) -> None:
        """Test that back_office role doesn't change already staff user."""
        user = UserFactory.create(is_staff=True)
        claim = {"roles": ["back_office"]}

        with patch.object(user, "save") as mock_save:
            link_auth_user(user, claim)
            # save() should not be called since user is already staff
            mock_save.assert_not_called()

    def test_link_auth_user_clears_existing_groups(self) -> None:
        """Test that existing groups are cleared before adding new ones."""
        user = UserFactory.create()
        old_group = Group.objects.create(name="old_group")
        new_group = Group.objects.create(name="new_group")

        # Add user to old group
        user.groups.add(old_group)
        assert old_group in user.groups.all()

        claim = {"roles": ["new_group"]}

        link_auth_user(user, claim)

        # Old group should be removed, new group added
        assert list(user.groups.all()) == [new_group]

    def test_link_auth_user_with_existing_groups(self) -> None:
        """Test that multiple existing groups are added correctly."""
        user = UserFactory.create()
        group1 = Group.objects.create(name="group1")
        group2 = Group.objects.create(name="group2")

        claim = {"roles": ["group1", "group2"]}

        link_auth_user(user, claim)

        user_groups = list(user.groups.all())
        assert group1 in user_groups
        assert group2 in user_groups
        assert len(user_groups) == 2

    def test_link_auth_user_nonexistent_group_logs_warning(self, caplog) -> None:
        """Test that nonexistent groups log a warning."""
        user = UserFactory.create()
        claim = {"roles": ["nonexistent_group"]}

        with caplog.at_level("WARNING"):
            link_auth_user(user, claim)

        assert "Group nonexistent_group from SSO does not exist" in caplog.text
        assert list(user.groups.all()) == []

    def test_link_auth_user_mixed_existing_and_nonexistent_groups(self, caplog) -> None:
        """Test with mix of existing and nonexistent groups."""
        user = UserFactory.create()
        existing_group = Group.objects.create(name="existing_group")

        claim = {"roles": ["existing_group", "nonexistent_group"]}

        with caplog.at_level("WARNING"):
            link_auth_user(user, claim)

        # Should add existing group and log warning for nonexistent
        assert list(user.groups.all()) == [existing_group]
        assert "Group nonexistent_group from SSO does not exist" in caplog.text

    def test_link_auth_user_empty_roles_list(self) -> None:
        """Test with empty roles list."""
        user = UserFactory.create()
        old_group = Group.objects.create(name="old_group")
        user.groups.add(old_group)

        claim = {"roles": []}

        link_auth_user(user, claim)

        # Groups should be cleared
        assert list(user.groups.all()) == []

    def test_link_auth_user_back_office_with_other_roles(self) -> None:
        """Test back_office role with other roles in comprehensive scenario."""
        user = UserFactory.create(is_staff=False)
        admin_group = Group.objects.create(name="admin")
        editor_group = Group.objects.create(name="editor")

        claim = {"roles": ["back_office", "admin", "editor"]}

        link_auth_user(user, claim)

        user.refresh_from_db()
        assert user.is_staff is True

        user_groups = set(user.groups.all())
        expected_groups = {admin_group, editor_group}
        assert user_groups == expected_groups
