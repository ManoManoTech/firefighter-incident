"""Hatchling build hook to run JS and CSS build steps with Rollup."""

from __future__ import annotations

import subprocess  # noqa: S404
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class RollupBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> Any:
        subprocess.check_output("npm install", shell=True)  # noqa: S602,S607
        subprocess.check_output("npm run build", shell=True)  # noqa: S602,S607
        return super().initialize(version, build_data)
