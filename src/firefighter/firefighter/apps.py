from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class FireFighter(AppConfig):
    name = "firefighter.firefighter"
    label = "firefighter"
    verbose_name = "FireFighter"

    def ready(self) -> None:
        from django.conf import settings

        import firefighter.components

        if settings.FF_SKIP_SECRET_KEY_CHECK:
            logger.info("Skipping SECRET_KEY check.")
            return

        env: str = settings.ENV
        secret_key: str = settings.SECRET_KEY

        if _entropy(secret_key) < 4:
            if env == "dev":
                logger.warning(
                    "SECRET_KEY is too weak, please change it to a stronger one. This is a warning for ENV=dev, but will raise an error in other environments."
                )
            else:
                raise ValueError(
                    "SECRET_KEY is too weak, please change it to a stronger one."
                )


def _entropy(value: str) -> float:
    """Calculate the entropy of a string."""
    import math
    import string

    if not value:
        return 0.0
    entropy: float = 0.0
    for x in string.printable:
        p_x = float(value.count(x)) / len(value)
        if p_x > 0:
            entropy += -p_x * math.log2(p_x)
    return entropy
