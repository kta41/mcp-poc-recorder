"""Runtime settings for PoC Recorder MCP, resolved from env vars and TOML config."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poc_recorder_mcp.config import load_config_data

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    width: int = 1440
    height: int = 900
    fps: int = 15
    show_cursor: bool = True
    show_hud: bool = True
    auto_install_browser: bool = False
    run_timeout_seconds: float = 180.0
    max_steps: int = 100
    max_concurrent_runs: int = 2
    output_dir: Path | None = None
    artifact_ttl_hours: float = 168.0
    artifact_max_files: int = 50
    allow_localhost: bool = True
    allowed_hosts: tuple[str, ...] = ()
    scenario_roots: tuple[Path, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict, compare=False)


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower() in _TRUE_VALUES


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_int(name: str) -> int | None:
    value = _env_float(name)
    return int(value) if value is not None else None


def _section_value(section: str, key: str, cwd: Path | None = None) -> Any:
    for data in load_config_data(cwd=cwd):
        value = data.get(section, {})
        if isinstance(value, dict) and key in value:
            return value[key]
    return None


def _resolve(explicit_env: Any, section: str, key: str, default: Any, cwd: Path | None = None) -> Any:
    if explicit_env is not None:
        return explicit_env
    configured = _section_value(section, key, cwd=cwd)
    if configured is not None:
        return configured
    return default


def load_settings(cwd: Path | None = None) -> Settings:
    """Build settings from env vars (priority) and the TOML config file."""
    output_dir_raw = os.environ.get("POC_RECORDER_MCP_OUTPUT_DIR") or _section_value("artifacts", "output_dir", cwd=cwd)
    output_dir = Path(output_dir_raw).expanduser() if isinstance(output_dir_raw, str) and output_dir_raw.strip() else None

    hosts_env = os.environ.get("POC_RECORDER_MCP_ALLOWED_HOSTS")
    if hosts_env is not None:
        allowed_hosts = tuple(h.strip().lower() for h in hosts_env.split(",") if h.strip())
    else:
        raw_hosts = _section_value("security", "allowed_hosts", cwd=cwd)
        allowed_hosts = tuple(str(h).strip().lower() for h in raw_hosts if str(h).strip()) if isinstance(raw_hosts, list) else ()

    roots_env = os.environ.get("POC_RECORDER_MCP_SCENARIO_ROOTS")
    if roots_env is not None:
        scenario_roots = tuple(Path(p.strip()).expanduser() for p in roots_env.split(",") if p.strip())
    else:
        raw_roots = _section_value("workspace", "scenario_roots", cwd=cwd)
        scenario_roots = (
            tuple(Path(str(p)).expanduser() for p in raw_roots if str(p).strip()) if isinstance(raw_roots, list) else ()
        )

    return Settings(
        width=int(_resolve(_env_int("POC_RECORDER_MCP_WIDTH"), "recorder", "width", 1440, cwd=cwd)),
        height=int(_resolve(_env_int("POC_RECORDER_MCP_HEIGHT"), "recorder", "height", 900, cwd=cwd)),
        fps=int(_resolve(_env_int("POC_RECORDER_MCP_FPS"), "recorder", "fps", 15, cwd=cwd)),
        show_cursor=bool(_resolve(_env_bool("POC_RECORDER_MCP_SHOW_CURSOR"), "recorder", "show_cursor", True, cwd=cwd)),
        show_hud=bool(_resolve(_env_bool("POC_RECORDER_MCP_SHOW_HUD"), "recorder", "show_hud", True, cwd=cwd)),
        auto_install_browser=bool(
            _resolve(_env_bool("POC_RECORDER_MCP_AUTO_INSTALL_BROWSER"), "recorder", "auto_install_browser", False, cwd=cwd)
        ),
        run_timeout_seconds=float(
            _resolve(_env_float("POC_RECORDER_MCP_RUN_TIMEOUT"), "limits", "run_timeout_seconds", 180.0, cwd=cwd)
        ),
        max_steps=int(_resolve(_env_int("POC_RECORDER_MCP_MAX_STEPS"), "limits", "max_steps", 100, cwd=cwd)),
        max_concurrent_runs=int(
            _resolve(_env_int("POC_RECORDER_MCP_MAX_CONCURRENT_RUNS"), "limits", "max_concurrent_runs", 2, cwd=cwd)
        ),
        output_dir=output_dir,
        artifact_ttl_hours=float(
            _resolve(_env_float("POC_RECORDER_MCP_ARTIFACT_TTL_HOURS"), "artifacts", "ttl_hours", 168.0, cwd=cwd)
        ),
        artifact_max_files=int(
            _resolve(_env_int("POC_RECORDER_MCP_ARTIFACT_MAX_FILES"), "artifacts", "max_files", 50, cwd=cwd)
        ),
        allow_localhost=bool(
            _resolve(_env_bool("POC_RECORDER_MCP_ALLOW_LOCALHOST"), "security", "allow_localhost", True, cwd=cwd)
        ),
        allowed_hosts=allowed_hosts,
        scenario_roots=scenario_roots,
    )
