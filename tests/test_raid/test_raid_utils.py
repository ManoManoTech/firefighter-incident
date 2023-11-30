from __future__ import annotations

import pytest

from firefighter.raid.utils import get_domain_from_email


def test_get_domain_from_email() -> None:
    assert get_domain_from_email("john.doe@example.com") == "example.com"
    assert get_domain_from_email("alice.bob@test.example.ORG") == "example.org"
    assert get_domain_from_email("webmaster@localhost") == "localhost"

    # Test with subdomains
    assert get_domain_from_email("info@subdomain.example.com") == "example.com"
    assert get_domain_from_email("user@sub.sub.example.net") == "example.net"

    # Test lowercase conversion
    assert get_domain_from_email("USER@EXAMPLE.COM") == "example.com"

    # Test with invalid inputs
    with pytest.raises(ValueError, match="Invalid email"):
        get_domain_from_email("invalidemail")
    with pytest.raises(ValueError, match="Invalid email"):
        assert get_domain_from_email("@") == ""
    with pytest.raises(ValueError, match="Invalid email"):
        assert get_domain_from_email("") == ""
