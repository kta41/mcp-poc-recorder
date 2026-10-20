"""Configuration loader for PoC Recorder MCP."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

CONFIG_FILENAME = "poc-recorder-mcp.toml"
GLOBAL_CONFIG_PATH = Path.home() / ".config" / "poc-recorder-mcp" / "config.toml"


def candidate_config_paths(cwd: Path | None = None) -> list[Path]:
    """Return ordered config file paths (explicit env, working directory, global)."""
    paths: list[Path] = []
    explicit = os.environ.get("POC_RECORDER_MCP_CONFIG")
    if explicit:
        paths.append(Path(explicit).expanduser())
    base = cwd or Path.cwd()
    paths.append(base / CONFIG_FILENAME)
    paths.append(GLOBAL_CONFIG_PATH)
    return paths


def load_config_data(cwd: Path | None = None) -> list[dict[str, Any]]:
    """Load all existing TOML configuration dictionaries in precedence order."""
    loaded: list[dict[str, Any]] = []
    for path in candidate_config_paths(cwd=cwd):
        if not path.is_file():
            continue
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
            if isinstance(data, dict):
                loaded.append(data)
        except OSError:
            continue
        except Exception:  # noqa: S112
            continue
    return loaded
