"""Pydantic models and input schemas for PoC Recorder MCP tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

UrlString = Annotated[str, StringConstraints(min_length=4, max_length=2048)]
PathString = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
ShortString = Annotated[str, StringConstraints(min_length=1, max_length=256)]
SelectorString = Annotated[str, StringConstraints(min_length=1, max_length=1024)]
OutputFormat = Literal["mp4", "gif", "both", "webm"]
StepAction = Literal[
    "goto",
    "wait",
    "click",
    "type",
    "fill",
    "select",
    "hover",
    "scroll",
    "press",
    "eval",
    "caption",
]


class MockRoute(BaseModel):
    url_pattern: ShortString = Field(
        description="Playwright URL glob or substring pattern to intercept (e.g. '**/api/tags' or '**/api/*').",
        examples=["**/api/tags"],
    )
    status: int = Field(default=200, ge=100, le=599, description="HTTP status code to return.")
    content_type: ShortString = Field(default="application/json", description="Response MIME type.")
    body: Any = Field(
        description="Response body (JSON-serializable dict/list or raw string) returned for matching requests."
    )


class HtmlReplacement(BaseModel):
    pattern: Annotated[str, StringConstraints(min_length=1, max_length=4096)] = Field(
        description="Regex or literal string to match inside the initial HTML document before the browser renders it."
    )
    replacement: str = Field(
        description="Replacement string injected into the HTML document (ideal for swapping embedded datasets with dummy data)."
    )
    is_regex: bool = Field(default=False, description="When true, treat `pattern` as a regular expression.")


class RecordingStep(BaseModel):
    action: StepAction = Field(
        description=(
            "Action type to perform: `goto`, `wait`, `click`, `type`, `fill`, `select`, "
            "`hover`, `scroll`, `press`, `eval`, or `caption`."
        )
    )
    selector: SelectorString | None = Field(
        default=None,
        description="CSS/Playwright selector for `click`, `type`, `fill`, `select`, or `hover` actions.",
        examples=["button.tab-btn:nth-of-type(2)", "#net-search"],
    )
    text: str | None = Field(
        default=None,
        description="Text to type/fill (`type`, `fill`), option value (`select`), key name (`press`), or target URL (`goto`).",
    )
    js: str | None = Field(
        default=None,
        description="JavaScript snippet to evaluate in the page context when `action == 'eval'`.",
    )
    caption: str | None = Field(
        default=None,
        description="Optional HUD subtitle banner shown at the bottom of the viewport during this step.",
    )
    ms: int = Field(
        default=900,
        ge=0,
        le=30000,
        description="Wait duration in milliseconds (for `wait` action) or pause after completing the step.",
    )
    delay_ms: int = Field(
        default=45,
        ge=0,
        le=500,
        description="Per-character keystroke delay in milliseconds when `action == 'type'`.",
    )
    x: int = Field(default=0, description="Horizontal scroll delta in pixels when `action == 'scroll'`.")
    y: int = Field(default=420, description="Vertical scroll delta in pixels when `action == 'scroll'`.")


class InspectPageParams(BaseModel):
    url: UrlString = Field(
        description="Target web service URL to inspect (e.g. `http://localhost:47891`).",
        examples=["http://localhost:47891"],
    )
    wait_ms: int = Field(
        default=600,
        ge=0,
        le=15000,
        description="Time in milliseconds to wait after networkidle before inspecting the DOM.",
    )
    max_elements: int = Field(
        default=60,
        ge=5,
        le=250,
        description="Maximum number of interactive DOM elements (buttons, inputs, tabs, links) to return.",
    )


class RecordPocParams(BaseModel):
    url: UrlString = Field(
        description="Target web service URL to record (e.g. `http://localhost:47891`).",
        examples=["http://localhost:47891"],
    )
    output_path: PathString = Field(
        description=(
            "Destination file path (or base path when `format='both'`). Relative paths resolve against "
            "the configured output directory or current working directory."
        ),
        examples=["/home/user/project/poc_demo.mp4"],
    )
    format: OutputFormat = Field(
        default="both",
        description="Output video format: `mp4` (H.264), `gif` (2-pass palette), `both` (generates .mp4 and .gif), or `webm`.",
    )
    steps: list[RecordingStep] = Field(
        default_factory=list,
        max_length=100,
        description="Ordered sequence of browser interactions to perform during the recording.",
    )
    width: int | None = Field(default=None, ge=320, le=3840, description="Viewport and video width in pixels (default 1440).")
    height: int | None = Field(default=None, ge=240, le=2160, description="Viewport and video height in pixels (default 900).")
    fps: int | None = Field(default=None, ge=5, le=60, description="Frame rate for GIF/MP4 conversion (default 15).")
    gif_width: int = Field(
        default=1280,
        ge=320,
        le=2560,
        description="Target width in pixels for GIF output (preserves aspect ratio with Lanczos scaling).",
    )
    show_cursor: bool | None = Field(
        default=None,
        description="Show animated virtual cursor and click ripples in the recording.",
    )
    show_hud: bool | None = Field(
        default=None,
        description="Show bottom HUD banner when steps include a `caption`.",
    )
    local_storage: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Key-value entries pre-populated into `window.localStorage` before page scripts run "
            "(values may be strings or JSON objects)."
        ),
    )
    session_storage: dict[str, Any] | None = Field(
        default=None,
        description="Key-value entries pre-populated into `window.sessionStorage` before page scripts run.",
    )
    init_script: str | None = Field(
        default=None,
        description="Optional JavaScript snippet injected via `context.add_init_script` before page load.",
    )
    post_load_js: str | None = Field(
        default=None,
        description=(
            "Optional JavaScript executed immediately after initial page load "
            "(e.g. to inject dummy datasets and re-render before choreography starts)."
        ),
    )
    mock_routes: list[MockRoute] | None = Field(
        default=None,
        max_length=50,
        description="Optional HTTP route mocks returning dummy JSON/text responses for matching requests.",
    )
    html_replacements: list[HtmlReplacement] | None = Field(
        default=None,
        max_length=20,
        description="Optional HTML response replacements applied on the fly to the main document before rendering.",
    )


class ListScenariosParams(BaseModel):
    root: PathString | None = Field(
        default=None,
        description="Optional directory to search for `*.scenario.json` files.",
    )
    query: ShortString | None = Field(
        default=None,
        description="Optional case-insensitive filter on scenario name or filename.",
    )


class RunScenarioParams(BaseModel):
    scenario: PathString = Field(
        description="Path to a `*.scenario.json` file defining `url`, `steps`, and optional dummy data overrides."
    )
    url: UrlString | None = Field(default=None, description="Optional override for the target URL.")
    output_path: PathString | None = Field(default=None, description="Optional override for the output path.")
    format: OutputFormat | None = Field(default=None, description="Optional override for output format (`mp4`, `gif`, `both`, `webm`).")


class ListRecordingsParams(BaseModel):
    directory: PathString | None = Field(
        default=None,
        description="Optional directory to scan for recorded `.mp4`, `.gif`, and `.webm` files.",
    )
    limit: int = Field(default=25, ge=1, le=200, description="Maximum number of recording entries to return.")


class ArtifactInfo(BaseModel):
    format: str
    path: str
    size_bytes: int
    size_kb: float


class ExecutionTimings(BaseModel):
    started: str
    completed: str
    duration_ms: int


class NormalizedResult(BaseModel):
    success: bool
    tool: str
    summary: dict[str, Any]
    artifacts: list[ArtifactInfo] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    timings: ExecutionTimings
