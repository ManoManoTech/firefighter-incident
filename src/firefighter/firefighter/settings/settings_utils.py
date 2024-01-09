from __future__ import annotations

from pathlib import Path

from decouple import AutoConfig

BASE_DIR = Path(__file__).parent.parent.parent

# Loading `.env` files with decouple
config = AutoConfig(search_path=BASE_DIR)

env: str = config("ENV", default="dev", cast=str)
env = env.strip()
_ENV = SETTINGS_ENV = env

if _ENV.lower() in {"prod", "prd", "support", "int"}:
    SETTINGS_ENV = "prod"
ENV = SETTINGS_ENV

# Commonly reused params
FF_VERSION: str | int = config("VERSION", default="dev")
APP_DISPLAY_NAME: str = config("APP_DISPLAY_NAME", default="FireFighter")
"""The name of the app. Used in the title of the app, and in the navigation bar."""
BASE_URL: str = config("BASE_URL")
"""The base URL of the app. Used for links in externals surfaces, like Slack or documents."""
