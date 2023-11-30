# Caching
# https://docs.djangoproject.com/en/4.2/topics/cache/
from __future__ import annotations

from firefighter.firefighter.settings.settings_utils import config

CACHE_URI = f"redis://{config('REDIS_HOST')}:{config('REDIS_PORT')}"

# DB INDEX 10 IS USED FOR CELERY
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CACHE_URI + "/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
            "SOCKET_TIMEOUT": 2,  # seconds
        },
    },
    "session": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CACHE_URI + "/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
            "SOCKET_TIMEOUT": 2,  # seconds
        },
    },
    "cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CACHE_URI + "/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,  # seconds
            "SOCKET_TIMEOUT": 2,  # seconds
        },
    },
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "session"
