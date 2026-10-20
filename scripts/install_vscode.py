from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "poc-recorder"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "poc-recorder-mcp" / "config.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Install PoC Recorder MCP for VS Code.")
    parser.add_argument(
        "--with-copilot-customizations",
        action="store_true",
        help="Also install the reusable Copilot prompt and agent in the user's global VS Code customization folders.",
    )
    parser.add_argument(
        "--install-browser",
        action="store_true",
        help="Ensure Playwright Headless Chromium is installed.",
    )
    parser.add_argument(
        "--vscode-user-dir",
        type=Path,
        default=default_vscode_user_dir(),
        help="VS Code user profile directory containing mcp.json.",
    )
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=Path.home() / ".config" / "github-copilot-prompts",
        help="Global Copilot prompts directory.",
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=Path.home() / ".config" / "github-copilot-agents",
        help="Global Copilot agents directory.",
    )
    parser.add_argument(
        "--vscode-prompt-dir",
        type=Path,
        default=Path.home() / ".vscode-server" / "data" / "User" / "prompts",
        help="VS Code user-level prompt/customization directory.",
    )
    parser.add_argument(
        "--vscode-agent-dir",
        type=Path,
        default=Path.home() / ".vscode-server" / "data" / "User" / "agents",
        help="VS Code user-level agents directory.",
    )
    args = parser.parse_args()

    if args.install_browser:
        ensure_playwright_browser()

    install_mcp_config(args.vscode_user_dir)
    install_remote_wsl_mcp_config()
    install_recorder_config(DEFAULT_CONFIG_PATH)

    if args.with_copilot_customizations:
        install_copilot_customizations(args.prompt_dir, args.agent_dir, args.vscode_prompt_dir, args.vscode_agent_dir)

    print("PoC Recorder MCP VS Code installation completed.")


def default_vscode_user_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Code" / "User"

    windows_user_dir = Path("/mnt/c/Users")
    username = os.environ.get("USER")
    if username and (windows_user_dir / username / "AppData" / "Roaming" / "Code" / "User").exists():
        return windows_user_dir / username / "AppData" / "Roaming" / "Code" / "User"

    return Path.home() / ".config" / "Code" / "User"


def build_server_config() -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": "uv",
        "args": ["--directory", str(PROJECT_ROOT), "run", "poc-recorder-mcp"],
    }


def install_mcp_config(vscode_user_dir: Path) -> None:
    vscode_user_dir.mkdir(parents=True, exist_ok=True)
    mcp_file = vscode_user_dir / "mcp.json"
    config = read_json_object(mcp_file)
    config.setdefault("servers", {})[SERVER_NAME] = build_server_config()
    write_json(mcp_file, config)
    print(f"Installed MCP server '{SERVER_NAME}' in {mcp_file}")


def install_remote_wsl_mcp_config() -> None:
    remote_user_dir = Path.home() / ".vscode-server" / "data" / "User"
    if not remote_user_dir.exists():
        return
    remote_user_dir.mkdir(parents=True, exist_ok=True)
    mcp_file = remote_user_dir / "mcp.json"
    config = read_json_object(mcp_file)
    config.setdefault("servers", {})[SERVER_NAME] = build_server_config()
    write_json(mcp_file, config)
    print(f"Installed MCP server '{SERVER_NAME}' in {mcp_file}")


def install_recorder_config(config_path: Path) -> None:
    if config_path.exists():
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    example = PROJECT_ROOT / "poc-recorder-mcp.example.toml"
    if example.exists():
        shutil.copy2(example, config_path)
        print(f"Created default config at {config_path}")


def install_copilot_customizations(
    prompt_dir: Path,
    agent_dir: Path,
    vscode_prompt_dir: Path,
    vscode_agent_dir: Path,
) -> None:
    src_prompt = PROJECT_ROOT / "copilot" / "prompts" / "record-web-poc.prompt.md"
    src_agent = PROJECT_ROOT / "copilot" / "agents" / "poc-recorder.agent.md"

    for target_p in (prompt_dir, vscode_prompt_dir):
        target_p.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_prompt, target_p / src_prompt.name)

    for target_a in (agent_dir, vscode_agent_dir):
        target_a.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_agent, target_a / src_agent.name)

    print("Installed Copilot prompt and agent customizations.")


def ensure_playwright_browser() -> None:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
