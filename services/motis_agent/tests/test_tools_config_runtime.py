from __future__ import annotations

import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

from motis_cli.tools_config import _get_platform_runtime_toolsets


def test_cli_runtime_toolsets_include_motis_core_by_default() -> None:
    toolsets = _get_platform_runtime_toolsets({}, "cli")

    assert "motis-finance" in toolsets
    assert "motis-operators" in toolsets
    assert "messaging" in toolsets


def test_cli_runtime_toolsets_preserve_motis_core_with_explicit_tool_config() -> None:
    config = {
        "platform_toolsets": {
            "cli": ["web", "terminal", "file"],
        }
    }

    toolsets = _get_platform_runtime_toolsets(
        config,
        "cli",
        include_default_mcp_servers=False,
    )

    assert {"web", "terminal", "file"}.issubset(toolsets)
    assert "motis-finance" in toolsets
    assert "motis-operators" in toolsets
    assert "messaging" in toolsets


def test_api_server_runtime_toolsets_stay_noninteractive() -> None:
    toolsets = _get_platform_runtime_toolsets({}, "api_server")

    assert "motis-finance" in toolsets
    assert "motis-operators" in toolsets
    assert "messaging" not in toolsets
