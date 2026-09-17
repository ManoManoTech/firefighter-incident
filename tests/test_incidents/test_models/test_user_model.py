from __future__ import annotations

import pytest

from firefighter.incidents.models.user import User


@pytest.mark.django_db
class TestGenerateUsername:
    """`username` is unique, so integrations that create users must supply one.

    Leaving it out makes every user land on the empty username and collide with
    the first one created that way, which silently broke the PagerDuty on-call
    sync for weeks.
    """

    def test_uses_the_email_local_part(self):
        assert User.objects.generate_username("john.doe@example.com") == "john.doe"

    def test_suffixes_when_the_local_part_is_taken(self):
        User.objects.create(email="john.doe@example.com", username="john.doe")

        username = User.objects.generate_username("john.doe@other.example.com")

        assert username != "john.doe"
        assert username.startswith("john.doe-")

    def test_never_returns_an_empty_username(self):
        assert User.objects.generate_username("@example.com") == "user"

    def test_fits_in_the_username_column(self):
        long_email = f"{'a' * 300}@example.com"

        username = User.objects.generate_username(long_email)

        max_length = User._meta.get_field("username").max_length
        assert max_length is not None
        assert len(username) <= max_length
