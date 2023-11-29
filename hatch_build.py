from __future__ import annotations

import subprocess
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class RollupBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> Any:
        subprocess.check_output("yarn install", shell=True)  # noqa: S602,S607
        subprocess.check_output("yarn run build", shell=True)  # noqa: S602,S607
        return super().initialize(version, build_data)
