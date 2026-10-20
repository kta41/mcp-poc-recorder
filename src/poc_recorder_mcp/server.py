"""MCP low-level server wiring for PoC Recorder MCP."""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

from poc_recorder_mcp.recorder import PocRecorder
from poc_recorder_mcp.types import (
    InspectPageParams,
    ListRecordingsParams,
    ListScenariosParams,
    RecordPocParams,
    RunScenarioParams,
)


def create_server(recorder: PocRecorder | None = None) -> Server:
    engine = recorder or PocRecorder()

    def json_text(result: Any) -> str:
        return json.dumps(result.model_dump(exclude_none=True), ensure_ascii=False, separators=(",", ":"))

    async def list_tools(_context: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name="inspect-page",
                    title="Inspect Web PoC Page",
                    description=(
                        "Open a target web service URL (including localhost ports) in headless Chromium and return "
                        "its title, headings, localStorage keys, and interactive DOM selectors (buttons, tabs, inputs, "
                        "chips, links). Use this before recording to discover accurate selectors."
                    ),
                    input_schema=InspectPageParams.model_json_schema(),
                ),
                types.Tool(
                    name="record-poc",
                    title="Record Web PoC Video (MP4 / GIF)",
                    description=(
                        "Record an automated video walkthrough of a web PoC or localhost service with an animated "
                        "virtual cursor, click ripples, optional step HUD captions, and dummy data injection "
                        "(localStorage, sessionStorage, HTTP route mocks, HTML replacements, or post-load JS). "
                        "Outputs H.264 `.mp4`, palette-optimized `.gif`, or `both`."
                    ),
                    input_schema=RecordPocParams.model_json_schema(),
                ),
                types.Tool(
                    name="list-scenarios",
                    title="List PoC Recording Scenarios",
                    description="Discover reusable `*.scenario.json` recording definitions under a directory or configured roots.",
                    input_schema=ListScenariosParams.model_json_schema(),
                ),
                types.Tool(
                    name="run-scenario",
                    title="Run PoC Recording Scenario",
                    description="Execute a saved `*.scenario.json` walkthrough with optional URL, output path, or format overrides.",
                    input_schema=RunScenarioParams.model_json_schema(),
                ),
                types.Tool(
                    name="list-recordings",
                    title="List Recorded Videos & GIFs",
                    description="List generated `.mp4`, `.gif`, and `.webm` files in the output directory with file sizes.",
                    input_schema=ListRecordingsParams.model_json_schema(),
                ),
            ]
        )

    async def call_tool(_context: Any, params: Any) -> types.CallToolResult:
        payload = params.arguments or {}
        if params.name == "inspect-page":
            res = await engine.inspect_page(InspectPageParams.model_validate(payload))
        elif params.name == "record-poc":
            res = await engine.record_poc(RecordPocParams.model_validate(payload))
        elif params.name == "list-scenarios":
            res = await engine.list_scenarios(ListScenariosParams.model_validate(payload))
        elif params.name == "run-scenario":
            res = await engine.run_scenario(RunScenarioParams.model_validate(payload))
        elif params.name == "list-recordings":
            res = await engine.list_recordings(ListRecordingsParams.model_validate(payload))
        else:
            raise ValueError(f"Unknown tool: {params.name}")
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json_text(res),
                )
            ]
        )

    return Server(
        name="poc-recorder",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )
