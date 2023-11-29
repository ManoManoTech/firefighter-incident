from __future__ import annotations

import logging
from functools import cache
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


@cache
def get_domain_from_email(email: str) -> str:
    """Returns the domain from an email address.

    Removes any subdomain(s) and the @, applies .lower().

    Args:
        email: The email address to extract the domain from.

    Returns:
        The domain part of the email address.

    Raises:
        ValueError: If the email is not well-formed.

    Examples:
      - `john.doe@example.com` => `example.com`
      - `alice.bob@test.example.ORG` => `example.org`
      - `webmaster@localhost` => `localhost`
    """
    # If there is not exactly one @, the email is invalid
    if email.count("@") != 1:
        msg = f"Invalid email: {email}"
        raise ValueError(msg)
    domain = email.split("@")[-1]
    if not domain:
        msg = f"Invalid email: {email}"
        raise ValueError(msg)
    domain_parts = domain.split(".")

    return (".".join(domain_parts[-2:]) if len(domain_parts) > 2 else domain).lower()
