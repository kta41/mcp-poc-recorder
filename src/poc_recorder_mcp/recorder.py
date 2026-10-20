"""Core Playwright browser inspection and PoC video recording engine."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Page, Route, async_playwright

from poc_recorder_mcp.converter import convert_recording
from poc_recorder_mcp.overlays import build_overlay_script, build_storage_script
from poc_recorder_mcp.settings import Settings, load_settings
from poc_recorder_mcp.types import (
    ArtifactInfo,
    ExecutionTimings,
    HtmlReplacement,
    InspectPageParams,
    ListRecordingsParams,
    ListScenariosParams,
    MockRoute,
    NormalizedResult,
    RecordingStep,
    RecordPocParams,
    RunScenarioParams,
)

LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}  # noqa: S104

DOM_INSPECTION_JS = """
(maxElements) => {
  const selectors = 'button, a[href], input, select, textarea, [role="tab"], [role="button"], .tab-btn, .chip, [onclick]';
  const nodes = Array.from(document.querySelectorAll(selectors));
  const seen = new Set();
  const elements = [];

  const uniqueSelector = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const tag = el.tagName.toLowerCase();
    if (el.getAttribute('name')) return `${tag}[name="${el.getAttribute('name')}"]`;
    const onclick = el.getAttribute('onclick');
    if (onclick && onclick.length < 80) return `${tag}[onclick*="${onclick.slice(0, 32).replace(/"/g, '\\"')}"]`;
    const parent = el.parentElement;
    if (parent) {
      const sameTag = Array.from(parent.children).filter(c => c.tagName === el.tagName);
      if (sameTag.length > 1) {
        const idx = sameTag.indexOf(el) + 1;
        const pSel = parent.id ? '#' + CSS.escape(parent.id) + ' > ' : '';
        return `${pSel}${tag}:nth-of-type(${idx})`;
      }
    }
    return tag;
  };

  for (const el of nodes) {
    if (elements.length >= maxElements) break;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    const sel = uniqueSelector(el);
    const text = (el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('title') || '').trim().slice(0, 80);
    const key = `${el.tagName}:${sel}:${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    elements.push({
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || null,
      id: el.id || null,
      selector: sel,
      text: text || null,
      visible: true
    });
  }

  const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
    .map(h => (h.innerText || '').trim())
    .filter(Boolean)
    .slice(0, 20);

  let storageKeys = [];
  try { storageKeys = Object.keys(window.localStorage); } catch (e) {}

  return {
    title: document.title,
    url: window.location.href,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    headings,
    local_storage_keys: storageKeys,
    interactive_elements: elements
  };
}
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_timings(started: datetime) -> ExecutionTimings:
    completed = _utc_now()
    duration_ms = max(0, int((completed - started).total_seconds() * 1000))
    return ExecutionTimings(
        started=started.isoformat().replace("+00:00", "Z"),
        completed=completed.isoformat().replace("+00:00", "Z"),
        duration_ms=duration_ms,
    )


def validate_target_url(url: str, settings: Settings) -> str:
    """Validate URL scheme and host policy."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http:// and https:// URLs are allowed.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"Invalid target URL '{url}': missing hostname.")
    if not settings.allow_localhost and host in LOCALHOST_HOSTS:
        raise ValueError(f"Recording localhost target '{host}' is disabled by security policy.")
    if settings.allowed_hosts and host not in settings.allowed_hosts:
        raise ValueError(f"Host '{host}' is not in the configured allowed_hosts list: {list(settings.allowed_hosts)}")
    return url


def resolve_output_path(raw_path: str, settings: Settings, cwd: Path | None = None) -> Path:
    """Resolve an output path relative to configured output_dir or cwd."""
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    base = settings.output_dir or ((cwd or Path.cwd()) / "build" / "recordings")
    return (base / candidate).resolve()


class PocRecorder:
    """Executes headless browser inspections and PoC video recordings."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()

    def _ensure_browser_if_configured(self) -> None:
        if not self.settings.auto_install_browser:
            return
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
            capture_output=True,
        )

    @staticmethod
    def _browser_launch_env() -> dict[str, str | float | bool]:
        """Build browser process environment, including user-space syslibs fallback on Linux."""
        env: dict[str, str | float | bool] = dict(os.environ)
        syslibs_root = Path.home() / ".cache" / "poc-recorder-mcp" / "syslibs" / "usr" / "lib"
        extra_dirs = [
            str(p)
            for p in (
                syslibs_root / "x86_64-linux-gnu",
                syslibs_root / "aarch64-linux-gnu",
                syslibs_root,
            )
            if p.is_dir()
        ]
        if extra_dirs:
            existing = str(env.get("LD_LIBRARY_PATH", ""))
            env["LD_LIBRARY_PATH"] = ":".join([*extra_dirs, *([existing] if existing else [])])
        return env

    async def _configure_routes(
        self,
        page: Page,
        mock_routes: list[MockRoute] | None,
        html_replacements: list[HtmlReplacement] | None,
    ) -> None:
        if mock_routes:
            for mock in mock_routes:
                body_str = mock.body if isinstance(mock.body, str) else json.dumps(mock.body, ensure_ascii=False)

                async def _handle_mock(
                    route: Route,
                    status: int = mock.status,
                    content_type: str = mock.content_type,
                    payload: str = body_str,
                ) -> None:
                    await route.fulfill(status=status, content_type=content_type, body=payload)

                await page.route(mock.url_pattern, _handle_mock)

        if html_replacements:
            replacements = list(html_replacements)

            async def _handle_doc(route: Route) -> None:
                if route.request.resource_type != "document":
                    await route.continue_()
                    return
                response = await route.fetch()
                text = await response.text()
                for rep in replacements:
                    text = re.sub(rep.pattern, rep.replacement, text) if rep.is_regex else text.replace(rep.pattern, rep.replacement)
                await route.fulfill(response=response, body=text)

            await page.route("**/*", _handle_doc)

    async def _execute_step(self, page: Page, step: RecordingStep, show_hud: bool) -> dict[str, Any]:
        if show_hud and step.caption is not None:
            await page.evaluate("([text]) => window.__mcpSetCaption && window.__mcpSetCaption(text)", [step.caption])

        act = step.action
        if act in {"wait", "caption"}:
            await page.wait_for_timeout(step.ms)
        elif act == "goto":
            if not step.text:
                raise ValueError("Step 'goto' requires `text` containing the destination URL.")
            validate_target_url(step.text, self.settings)
            await page.goto(step.text, wait_until="networkidle")
            await page.wait_for_timeout(step.ms)
        elif act == "click":
            if not step.selector:
                raise ValueError("Step 'click' requires `selector`.")
            loc = page.locator(step.selector).first
            await loc.scroll_into_view_if_needed(timeout=5000)
            box = await loc.bounding_box()
            if box:
                await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=14)
                await page.wait_for_timeout(120)
            await loc.click(timeout=5000)
            await page.wait_for_timeout(step.ms)
        elif act == "hover":
            if not step.selector:
                raise ValueError("Step 'hover' requires `selector`.")
            loc = page.locator(step.selector).first
            await loc.scroll_into_view_if_needed(timeout=5000)
            box = await loc.bounding_box()
            if box:
                await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=14)
            await loc.hover(timeout=5000)
            await page.wait_for_timeout(step.ms)
        elif act == "type":
            if not step.selector:
                raise ValueError("Step 'type' requires `selector`.")
            loc = page.locator(step.selector).first
            await loc.scroll_into_view_if_needed(timeout=5000)
            box = await loc.bounding_box()
            if box:
                await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=12)
            await loc.click(timeout=5000)
            await loc.fill("")
            if step.text:
                await loc.press_sequentially(step.text, delay=step.delay_ms)
            await page.wait_for_timeout(step.ms)
        elif act == "fill":
            if not step.selector:
                raise ValueError("Step 'fill' requires `selector`.")
            loc = page.locator(step.selector).first
            await loc.fill(step.text or "", timeout=5000)
            await page.wait_for_timeout(step.ms)
        elif act == "select":
            if not step.selector or step.text is None:
                raise ValueError("Step 'select' requires `selector` and `text` (option value).")
            loc = page.locator(step.selector).first
            await loc.select_option(step.text, timeout=5000)
            await page.wait_for_timeout(step.ms)
        elif act == "scroll":
            await page.mouse.wheel(step.x, step.y)
            await page.wait_for_timeout(step.ms)
        elif act == "press":
            if not step.text:
                raise ValueError("Step 'press' requires `text` containing the key name (e.g. 'Escape', 'Enter').")
            await page.keyboard.press(step.text)
            await page.wait_for_timeout(step.ms)
        elif act == "eval":
            if not step.js:
                raise ValueError("Step 'eval' requires `js`.")
            await page.evaluate(step.js)
            await page.wait_for_timeout(step.ms)

        return {"action": act, "selector": step.selector, "caption": step.caption, "status": "ok"}

    async def inspect_page(self, params: InspectPageParams) -> NormalizedResult:
        """Inspect a live page and return interactive selectors and metadata."""
        started = _utc_now()
        try:
            validate_target_url(params.url, self.settings)
            self._ensure_browser_if_configured()
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, env=self._browser_launch_env())
                try:
                    context = await browser.new_context(
                        viewport={"width": self.settings.width, "height": self.settings.height}
                    )
                    page = await context.new_page()
                    await page.goto(params.url, wait_until="networkidle", timeout=int(self.settings.run_timeout_seconds * 1000))
                    if params.wait_ms > 0:
                        await page.wait_for_timeout(params.wait_ms)
                    info = await page.evaluate(DOM_INSPECTION_JS, params.max_elements)
                finally:
                    await browser.close()

            elements = info.get("interactive_elements", [])
            return NormalizedResult(
                success=True,
                tool="inspect-page",
                summary={
                    "url": info.get("url", params.url),
                    "title": info.get("title", ""),
                    "interactive_count": len(elements),
                    "headings_count": len(info.get("headings", [])),
                },
                details=info,
                timings=_build_timings(started),
            )
        except Exception as exc:
            return NormalizedResult(
                success=False,
                tool="inspect-page",
                summary={"url": params.url, "interactive_count": 0},
                error=str(exc),
                timings=_build_timings(started),
            )

    async def record_poc(self, params: RecordPocParams) -> NormalizedResult:
        """Record an automated browser walkthrough and convert it to MP4 and/or GIF."""
        started = _utc_now()
        tmp_dir = Path(tempfile.mkdtemp(prefix="poc_recorder_"))
        warnings: list[str] = []
        executed_steps: list[dict[str, Any]] = []

        try:
            validate_target_url(params.url, self.settings)
            if len(params.steps) > self.settings.max_steps:
                raise ValueError(f"Step count ({len(params.steps)}) exceeds configured max_steps ({self.settings.max_steps}).")

            width = params.width or self.settings.width
            height = params.height or self.settings.height
            fps = params.fps or self.settings.fps
            show_cursor = self.settings.show_cursor if params.show_cursor is None else params.show_cursor
            show_hud = self.settings.show_hud if params.show_hud is None else params.show_hud
            out_path = resolve_output_path(params.output_path, self.settings)

            self._ensure_browser_if_configured()

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, env=self._browser_launch_env())
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    record_video_dir=str(tmp_dir),
                    record_video_size={"width": width, "height": height},
                    device_scale_factor=1,
                )

                storage_script = build_storage_script(params.local_storage, params.session_storage)
                if storage_script:
                    await context.add_init_script(storage_script)

                await context.add_init_script(build_overlay_script(show_cursor=show_cursor, show_hud=show_hud))

                if params.init_script:
                    await context.add_init_script(params.init_script)

                page = await context.new_page()
                await self._configure_routes(page, params.mock_routes, params.html_replacements)

                await page.goto(params.url, wait_until="networkidle", timeout=int(self.settings.run_timeout_seconds * 1000))
                if params.post_load_js:
                    await page.evaluate(params.post_load_js)
                await page.wait_for_timeout(650)

                for idx, step in enumerate(params.steps, start=1):
                    try:
                        res = await self._execute_step(page, step, show_hud=show_hud)
                        res["step_index"] = idx
                        executed_steps.append(res)
                    except Exception as step_exc:
                        warnings.append(f"Step {idx} ({step.action} {step.selector or ''}) warning: {step_exc}")
                        executed_steps.append(
                            {
                                "step_index": idx,
                                "action": step.action,
                                "selector": step.selector,
                                "status": "warning",
                                "message": str(step_exc),
                            }
                        )

                await page.wait_for_timeout(850)
                video = page.video
                page_title = await page.title()
                await context.close()
                await browser.close()

                if video is None:
                    raise RuntimeError("Playwright did not produce a video stream for the recording context.")
                webm_path = Path(await video.path())

            artifacts = convert_recording(
                webm_path=webm_path,
                base_output_path=out_path,
                fmt=params.format,
                width=width,
                gif_width=min(params.gif_width, width),
                fps=fps,
            )

            return NormalizedResult(
                success=True,
                tool="record-poc",
                summary={
                    "url": params.url,
                    "title": page_title,
                    "format": params.format,
                    "viewport": f"{width}x{height}",
                    "fps": fps,
                    "steps_total": len(params.steps),
                    "steps_completed": sum(1 for s in executed_steps if s.get("status") == "ok"),
                    "artifacts_count": len(artifacts),
                },
                artifacts=artifacts,
                details={"steps": executed_steps},
                warnings=warnings,
                timings=_build_timings(started),
            )
        except Exception as exc:
            return NormalizedResult(
                success=False,
                tool="record-poc",
                summary={"url": params.url, "steps_total": len(params.steps), "artifacts_count": 0},
                details={"steps": executed_steps},
                warnings=warnings,
                error=str(exc),
                timings=_build_timings(started),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def list_scenarios(self, params: ListScenariosParams) -> NormalizedResult:
        """List reusable `*.scenario.json` files."""
        started = _utc_now()
        roots: list[Path] = []
        if params.root:
            roots.append(Path(params.root).expanduser().resolve())
        elif self.settings.scenario_roots:
            roots.extend(r.resolve() for r in self.settings.scenario_roots if r.exists())
        else:
            roots.append(Path.cwd())

        found: list[dict[str, Any]] = []
        q = (params.query or "").strip().lower()
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.scenario.json")):
                if q and q not in path.name.lower() and q not in str(path).lower():
                    continue
                found.append({"name": path.name.removesuffix(".scenario.json"), "path": str(path.resolve())})

        return NormalizedResult(
            success=True,
            tool="list-scenarios",
            summary={"count": len(found), "roots": [str(r) for r in roots]},
            details={"scenarios": found},
            timings=_build_timings(started),
        )

    async def run_scenario(self, params: RunScenarioParams) -> NormalizedResult:
        """Load a `*.scenario.json` file and execute `record_poc` with optional overrides."""
        started = _utc_now()
        scenario_path = Path(params.scenario).expanduser().resolve()
        if not scenario_path.is_file():
            return NormalizedResult(
                success=False,
                tool="run-scenario",
                summary={"scenario": str(scenario_path)},
                error=f"Scenario file not found: {scenario_path}",
                timings=_build_timings(started),
            )
        try:
            raw = json.loads(scenario_path.read_text(encoding="utf-8"))
            if params.url:
                raw["url"] = params.url
            if params.output_path:
                raw["output_path"] = params.output_path
            if params.format:
                raw["format"] = params.format
            rec_params = RecordPocParams.model_validate(raw)
            res = await self.record_poc(rec_params)
            res.tool = "run-scenario"
            res.summary["scenario"] = str(scenario_path)
            return res
        except Exception as exc:
            return NormalizedResult(
                success=False,
                tool="run-scenario",
                summary={"scenario": str(scenario_path)},
                error=str(exc),
                timings=_build_timings(started),
            )

    async def list_recordings(self, params: ListRecordingsParams) -> NormalizedResult:
        """List generated `.mp4`, `.gif`, and `.webm` recordings."""
        started = _utc_now()
        target_dir = (
            Path(params.directory).expanduser().resolve()
            if params.directory
            else (self.settings.output_dir or Path.cwd())
        )
        artifacts: list[ArtifactInfo] = []
        if target_dir.is_dir():
            files = [
                p
                for p in target_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".mp4", ".gif", ".webm"}
            ]
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for f in files[: params.limit]:
                sz = f.stat().st_size
                artifacts.append(
                    ArtifactInfo(
                        format=f.suffix.lstrip(".").lower(),
                        path=str(f.resolve()),
                        size_bytes=sz,
                        size_kb=round(sz / 1024.0, 2),
                    )
                )
        return NormalizedResult(
            success=True,
            tool="list-recordings",
            summary={"directory": str(target_dir), "count": len(artifacts)},
            artifacts=artifacts,
            timings=_build_timings(started),
        )
