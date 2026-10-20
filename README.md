# 🎬 PoC Recorder MCP Server for Python

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-Enabled-blue?style=for-the-badge)](https://modelcontextprotocol.io/)
[![Playwright](https://img.shields.io/badge/Playwright-Headless_Chromium-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-MP4_%26_GIF-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

> Python MCP server for inspecting web PoCs and recording automated, client-ready `.mp4` and `.gif` walkthroughs of `localhost` or remote web services. It exposes a Model Context Protocol server over `stdio` powered by Headless Chromium (Playwright) and FFmpeg.

*Note: All examples in this repository use placeholder URLs and paths (`http://localhost:47891`, `/home/user/project/scenarios`, `acme-corp.test`). Replace them with your own target URLs and output directories.*

---

## ✨ Features

* **Record Web PoCs to MP4 & GIF:** Capture smooth headless Chromium walkthroughs and transcode them automatically into H.264 `.mp4` (`yuv420p` + `faststart`) and two-pass palette-optimized `.gif` (`palettegen` + `paletteuse`).
* **Visual Cursor & Click Ripples:** Injects an animated virtual pointer with click ripple effects and smooth mouse trajectories (`page.mouse.move`), solving Playwright's native invisible-cursor limitation.
* **Step HUD Captions:** Optional translucent subtitle pill at the bottom of the viewport (`caption` per step) to guide clients through each feature being demonstrated.
* **Zero-Leak Dummy Data Injection:** Replace real telemetry or development data before frame 0 using `local_storage`, `session_storage`, `mock_routes` (HTTP API interception), `html_replacements` (on-the-fly document rewriting), or `post_load_js`.
* **Live DOM Selector Discovery:** Inspect any `localhost` or remote URL with `inspect-page` to retrieve verified CSS selectors for tabs, buttons, inputs, and filter chips before recording.
* **Reusable Scenario Files:** Store and replay repeatable `*.scenario.json` demo flows across builds.
* **Zero System-FFmpeg Requirement:** Uses system `ffmpeg` when available on `PATH` and transparently falls back to the bundled static binary from `imageio-ffmpeg`.
* **Normalized Outputs:** Return structured JSON results containing `success`, `summary`, `artifacts`, `details`, `warnings`, and `timings`.

---

## 📦 Requirements

* **Python:** 3.10 or newer
* **Package Manager:** `uv`
* **Browser Engine:** Playwright Chromium

Install the Chromium browser binary once via `uv`:

```bash
uv run playwright install chromium
```

Runtime auto-install is also available as an opt-in setting: set `POC_RECORDER_MCP_AUTO_INSTALL_BROWSER=1` (or `auto_install_browser = true` under `[recorder]` in `poc-recorder-mcp.toml`).

---

## 🚀 Installation & Running

### 1. Installation
Install dependencies using `uv`:

```bash
uv sync
uv run playwright install chromium
```
*(If your configured package index does not mirror the MCP Python SDK, point uv at PyPI for the sync: `UV_DEFAULT_INDEX=https://pypi.org/simple uv sync`)*

### 2. Running the Server
You can run the server directly using `uv`:

```bash
uv run poc-recorder-mcp
```
*Alternatively, run the module directly inside the uv environment: `uv run python -m poc_recorder_mcp`*

---

## ⚙️ Configuration

### MCP Configuration
Example MCP `stdio` configuration from this workspace root:

```json
{
  "mcpServers": {
    "poc-recorder": {
      "command": "uv",
      "args": ["run", "poc-recorder-mcp"]
    }
  }
}
```

### Configuration File (`poc-recorder-mcp.toml`)
Default viewport settings, limits, and scenario roots can be configured in `poc-recorder-mcp.toml` in the current working directory, or globally in `~/.config/poc-recorder-mcp/config.toml`.

See `poc-recorder-mcp.example.toml` for a commented template:

```toml
[workspace]
scenario_roots = [
  "/home/user/project/scenarios"
]

[recorder]
width = 1440
height = 900
fps = 15
show_cursor = true
show_hud = true
auto_install_browser = false

[limits]
run_timeout_seconds = 180
max_steps = 100
max_concurrent_runs = 2

[artifacts]
ttl_hours = 168
max_files = 50

[security]
allow_localhost = true
allowed_hosts = []
```

Every setting can also be set via environment variables (`POC_RECORDER_MCP_WIDTH`, `POC_RECORDER_MCP_HEIGHT`, `POC_RECORDER_MCP_FPS`, `POC_RECORDER_MCP_SHOW_CURSOR`, `POC_RECORDER_MCP_SHOW_HUD`, `POC_RECORDER_MCP_AUTO_INSTALL_BROWSER`, `POC_RECORDER_MCP_RUN_TIMEOUT`, `POC_RECORDER_MCP_MAX_STEPS`, `POC_RECORDER_MCP_MAX_CONCURRENT_RUNS`, `POC_RECORDER_MCP_OUTPUT_DIR`, `POC_RECORDER_MCP_ALLOW_LOCALHOST`, `POC_RECORDER_MCP_ALLOWED_HOSTS`, `POC_RECORDER_MCP_SCENARIO_ROOTS`, `POC_RECORDER_MCP_LOG_LEVEL`), which take precedence over the file.

> **Note:** The installer creates `~/.config/poc-recorder-mcp/config.toml` from the template. Local `poc-recorder-mcp.toml` files and recorded `*.mp4` / `*.gif` / `*.webm` files are git-ignored so local demos and paths are never committed accidentally.

---

## 💻 Local VS Code Installation

From the project root, install dependencies with `uv`:

```bash
UV_DEFAULT_INDEX=https://pypi.org/simple uv sync
uv run playwright install chromium
```

This repository includes `.vscode/mcp.json`, allowing VS Code to discover the local MCP server from the workspace:

```json
{
  "servers": {
    "poc-recorder": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "poc-recorder-mcp"]
    }
  }
}
```

Reload the VS Code window after syncing dependencies. The `poc-recorder` server should now be available in the MCP servers list.

### Global Installation
To install the MCP server in the VS Code user profile so it is available from **any** workspace:

```bash
uv run python scripts/install_vscode.py
```
*(To also install the reusable Copilot prompt and agent globally, append `--with-copilot-customizations` to the command above).*

To install it manually in another local VS Code workspace, change the command args to include `--directory`:

```json
"args": ["--directory", "/home/user/mcp-poc-recorder", "run", "poc-recorder-mcp"]
```

---

## 🧰 Available Tools

### 🔍 `inspect-page`
Opens a target web service (`http://localhost:<port>` or remote URL) in headless Chromium and returns the page title, headings, `localStorage` keys, and interactive DOM elements (`button`, `input`, `select`, `.tab-btn`, `.chip`, `[onclick]`) with verified CSS selectors.
* **`url`** *(required)*: Target URL to inspect.
* **`wait_ms`** *(optional)*: Delay after `networkidle` before extracting DOM metadata (default `600`).
* **`max_elements`** *(optional)*: Maximum interactive elements to return (default `60`).

### 🎥 `record-poc`
Records an automated browser walkthrough with a virtual cursor, click ripples, HUD step captions, and dummy data injection, then converts the recording to `.mp4`, `.gif`, or `both`.
* **`url`** *(required)*: Target web service URL (e.g. `http://localhost:47891`).
* **`output_path`** *(required)*: Output file path (or base path when `format="both"`).
* **`format`** *(optional)*: `"both"` (default — emits `.mp4` and `.gif`), `"mp4"`, `"gif"`, or `"webm"`.
* **`steps`** *(optional)*: Ordered list of actions (`goto`, `wait`, `click`, `type`, `fill`, `select`, `hover`, `scroll`, `press`, `eval`, `caption`).
* **`local_storage` / `session_storage`** *(optional)*: Key-value pairs pre-loaded into browser storage before page scripts execute.
* **`mock_routes`** *(optional)*: Intercept matching HTTP requests and fulfill them with synthetic JSON/text payloads.
* **`html_replacements`** *(optional)*: Rewrite inline datasets or strings in the main HTML document before rendering.
* **`post_load_js`** *(optional)*: JavaScript executed right after initial navigation to hydrate dummy state before choreography steps begin.

<details>
<summary><b>View detailed dummy-data injection & step choreography options</b></summary>

**Supported Step Actions:**
* `{"action": "click", "selector": "button.tab-btn:nth-of-type(2)", "caption": "2. Network Intelligence", "ms": 1100}`
* `{"action": "type", "selector": "#net-search", "text": "ACME-Corp", "delay_ms": 45, "ms": 900}`
* `{"action": "hover", "selector": ".badge.b-suspicious", "ms": 800}`
* `{"action": "scroll", "x": 0, "y": 420, "ms": 800}`
* `{"action": "eval", "js": "openNetworkDossier('00:11:22:33:44:55')", "ms": 1200}`
* `{"action": "press", "text": "Escape", "ms": 600}`
* `{"action": "wait", "ms": 1500, "caption": "Executive Risk Overview"}`

**Example `record-poc` payload with dummy data:**
```json
{
  "url": "http://localhost:47891",
  "output_path": "/home/user/project/poc_demo",
  "format": "both",
  "local_storage": {
    "demo_mode": "true"
  },
  "mock_routes": [
    {
      "url_pattern": "**/api/tags",
      "status": 200,
      "body": {"networks": {"00:11:22:33:44:55": {"label": "ACME-HQ-AP01", "category": "PROPIO"}}}
    }
  ],
  "steps": [
    {"action": "wait", "ms": 1200, "caption": "1. Executive Dashboard — Synthetic Audit Dataset"},
    {"action": "click", "selector": "nav.tabs button:nth-of-type(2)", "ms": 1200, "caption": "2. Inspecting Discovered Access Points"}
  ]
}
```
</details>

### 📋 `list-scenarios` & `run-scenario`
* `list-scenarios`: Discovers reusable `*.scenario.json` walkthrough files under a directory or configured `scenario_roots`.
* `run-scenario`: Executes a saved `*.scenario.json` file with optional `url`, `output_path`, and `format` overrides.

### 📁 `list-recordings`
Lists generated `.mp4`, `.gif`, and `.webm` artifacts in the output directory with file sizes in bytes and KB.

---

## Agent Skills & Copilot Integration

These workflows use the MCP server configured as `poc-recorder`; installing a skill or prompt does not install or configure the server. Configure the server in your client first using the MCP configuration above.

### VS Code GitHub Copilot

The repository includes a [custom agent](copilot/agents/poc-recorder.agent.md) and a [slash-command prompt](copilot/prompts/record-web-poc.prompt.md). From this repository root, copy them into the target workspace:

```bash
mkdir -p /path/to/workspace/.github/agents /path/to/workspace/.github/prompts
cp copilot/agents/poc-recorder.agent.md /path/to/workspace/.github/agents/
cp copilot/prompts/record-web-poc.prompt.md /path/to/workspace/.github/prompts/
```

Select the `poc-recorder` custom agent in Copilot Chat's agent picker (`@poc-recorder` where supported), or run `/record-web-poc <url> [output_path]` in Chat.

Alternatively, install both globally with:

```bash
uv run python scripts/install_vscode.py --with-copilot-customizations
```

### Claude Code / Cursor / Windsurf

The universal [PoC Recorder skill](skills/poc-recorder/SKILL.md) consolidates DOM inspection, zero-leak dummy data injection, cursor choreography, and dual MP4/GIF generation.

For Claude Code, copy it into the target project's skill directory:

```bash
mkdir -p /path/to/workspace/.claude/skills/poc-recorder
cp skills/poc-recorder/SKILL.md /path/to/workspace/.claude/skills/poc-recorder/SKILL.md
```

Or symlink the skill directory using an absolute source path:

```bash
mkdir -p /path/to/workspace/.claude/skills
ln -s /absolute/path/to/mcp-poc-recorder/skills/poc-recorder /path/to/workspace/.claude/skills/poc-recorder
```

For Cursor, copy or symlink the same directory to `.cursor/skills/poc-recorder/`; for Windsurf, use `.windsurf/skills/poc-recorder/` in the target workspace.

### Repository Assets

Skills and Copilot templates remain organized under `skills/` and `copilot/` at the repository root, separately from the Python packages discovered under `src/` in `pyproject.toml`.

Execution results retain the server's normalized output contract:

```json
{
  "success": true,
  "tool": "record-poc",
  "summary": {
    "url": "http://localhost:47891",
    "title": "SIGINT Wireless Intelligence Console — Wardrive ESP32-S3",
    "format": "both",
    "viewport": "1440x900",
    "fps": 15,
    "steps_total": 8,
    "steps_completed": 8,
    "artifacts_count": 2
  },
  "artifacts": [
    {
      "format": "mp4",
      "path": "/home/user/project/poc_demo.mp4",
      "size_bytes": 412890,
      "size_kb": 403.21
    },
    {
      "format": "gif",
      "path": "/home/user/project/poc_demo.gif",
      "size_bytes": 1154320,
      "size_kb": 1127.27
    }
  ],
  "details": {
    "steps": []
  },
  "warnings": [],
  "timings": {
    "started": "2026-10-20T17:20:00.000000Z",
    "completed": "2026-10-20T17:20:14.000000Z",
    "duration_ms": 14000
  }
}
```

---

## 🐳 Docker

The Docker image installs this Python server, FFmpeg, and Headless Chromium:

```bash
docker build -t poc-recorder-mcp-python .
docker run --rm -i --network host poc-recorder-mcp-python
```

---

## 🛠️ Development & Project Structure

**Commands:**
* Compile-check the sources: `uv run python -m compileall src`
* Lint with Ruff: `uv run ruff check src tests scripts`
* Type-check with Mypy: `uv run mypy src/poc_recorder_mcp`
* Run the test suite: `uv run pytest tests/ -q`

**Structure:**
```text
.
├── src/poc_recorder_mcp/      # MCP server, Playwright recorder, FFmpeg converter, overlays, and types
├── scripts/                   # VS Code installer script
├── copilot/                   # Reusable Copilot prompt and agent templates
├── skills/poc-recorder/       # Universal Agent Skill (SKILL.md)
├── tests/                     # Unit tests
├── .vscode/mcp.json           # Workspace MCP server entry
└── poc-recorder-mcp.example.toml # Commented configuration template
```
---
mcp-name: io.github.kta41/mcp-poc-recorder
---

## 📄 License
Released under the [MIT License](LICENSE).
