"""Unit tests for PoC Recorder MCP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from poc_recorder_mcp.converter import convert_recording, resolve_ffmpeg_binary
from poc_recorder_mcp.overlays import build_overlay_script, build_storage_script
from poc_recorder_mcp.recorder import PocRecorder, resolve_output_path, validate_target_url
from poc_recorder_mcp.server import create_server
from poc_recorder_mcp.settings import Settings, load_settings
from poc_recorder_mcp.types import (
    ArtifactInfo,
    ListRecordingsParams,
    ListScenariosParams,
    RecordingStep,
    RecordPocParams,
    RunScenarioParams,
)


class TestSettingsAndValidation:
    def test_load_settings_from_toml(self, tmp_path: Path) -> None:
        toml_file = tmp_path / "poc-recorder-mcp.toml"
        toml_file.write_text(
            "[recorder]\nwidth = 1280\nheight = 720\nfps = 20\nshow_cursor = false\n"
            '[security]\nallow_localhost = false\nallowed_hosts = ["example.com"]\n',
            encoding="utf-8",
        )
        settings = load_settings(cwd=tmp_path)
        assert settings.width == 1280
        assert settings.height == 720
        assert settings.fps == 20
        assert settings.show_cursor is False
        assert settings.allow_localhost is False
        assert settings.allowed_hosts == ("example.com",)

    def test_validate_target_url_localhost_allowed_by_default(self) -> None:
        settings = Settings()
        assert validate_target_url("http://localhost:47891/index.html", settings) == "http://localhost:47891/index.html"
        assert validate_target_url("http://127.0.0.1:8080", settings) == "http://127.0.0.1:8080"

    def test_validate_target_url_rejects_bad_scheme_and_disallowed_localhost(self) -> None:
        settings = Settings(allow_localhost=False, allowed_hosts=("demo.example.com",))
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            validate_target_url("file:///etc/passwd", settings)
        with pytest.raises(ValueError, match="disabled by security policy"):
            validate_target_url("http://localhost:47891", settings)
        with pytest.raises(ValueError, match="allowed_hosts"):
            validate_target_url("https://other.example.com", settings)
        assert validate_target_url("https://demo.example.com/app", settings) == "https://demo.example.com/app"

    def test_resolve_output_path(self, tmp_path: Path) -> None:
        settings = Settings(output_dir=tmp_path)
        resolved = resolve_output_path("demo_video.mp4", settings)
        assert resolved == (tmp_path / "demo_video.mp4").resolve()


class TestOverlaysAndStorage:
    def test_build_overlay_script_flags(self) -> None:
        script = build_overlay_script(show_cursor=True, show_hud=False)
        assert "window.__mcpShowCursor = true;" in script
        assert "window.__mcpShowHud = false;" in script
        assert "__mcp_poc_cursor" in script

    def test_build_storage_script_serializes_dicts_and_strings(self) -> None:
        assert build_storage_script(None, None) is None
        script = build_storage_script(
            local_storage={"plain": "hello", "nested": {"count": 3}},
            session_storage={"token": "dummy"},
        )
        assert script is not None
        assert '"plain": "hello"' in script
        assert '\\"count\\": 3' in script


class TestConverterAndRecorderHelpers:
    def test_resolve_ffmpeg_binary_returns_valid_executable(self) -> None:
        binary = resolve_ffmpeg_binary()
        assert binary
        assert Path(binary).exists()

    def test_convert_recording_webm_copy(self, tmp_path: Path) -> None:
        dummy_webm = tmp_path / "raw.webm"
        dummy_webm.write_bytes(b"WEBM_TEST_BYTES")
        out_base = tmp_path / "output_demo"
        artifacts = convert_recording(dummy_webm, out_base, fmt="webm")
        assert len(artifacts) == 1
        assert artifacts[0].format == "webm"
        assert Path(artifacts[0].path).read_bytes() == b"WEBM_TEST_BYTES"

    def test_convert_recording_both_calls_mp4_and_gif(self, tmp_path: Path) -> None:
        dummy_webm = tmp_path / "raw.webm"
        dummy_webm.write_bytes(b"WEBM_TEST_BYTES")
        out_base = tmp_path / "output_demo.mp4"
        fake_mp4 = ArtifactInfo(format="mp4", path=str(tmp_path / "output_demo.mp4"), size_bytes=1024, size_kb=1.0)
        fake_gif = ArtifactInfo(format="gif", path=str(tmp_path / "output_demo.gif"), size_bytes=2048, size_kb=2.0)

        with (
            patch("poc_recorder_mcp.converter.transcode_to_mp4", return_value=fake_mp4) as m_mp4,
            patch("poc_recorder_mcp.converter.transcode_to_gif", return_value=fake_gif) as m_gif,
        ):
            artifacts = convert_recording(dummy_webm, out_base, fmt="both", width=1440, gif_width=1280, fps=15)

        assert len(artifacts) == 2
        m_mp4.assert_called_once()
        m_gif.assert_called_once()

    def test_list_scenarios_and_recordings(self, tmp_path: Path) -> None:
        scen_file = tmp_path / "sigint_audit.scenario.json"
        scen_file.write_text(
            json.dumps({"url": "http://localhost:47891", "output_path": str(tmp_path / "out.mp4"), "steps": []}),
            encoding="utf-8",
        )
        mp4_file = tmp_path / "sample.mp4"
        mp4_file.write_bytes(b"0" * 4096)

        recorder = PocRecorder(Settings(output_dir=tmp_path, scenario_roots=(tmp_path,)))
        scen_res = asyncio.run(recorder.list_scenarios(ListScenariosParams(query="sigint")))
        assert scen_res.success is True
        assert scen_res.summary["count"] == 1
        assert scen_res.details["scenarios"][0]["name"] == "sigint_audit"

        rec_res = asyncio.run(recorder.list_recordings(ListRecordingsParams(directory=str(tmp_path))))
        assert rec_res.success is True
        assert rec_res.summary["count"] == 1
        assert rec_res.artifacts[0].format == "mp4"

    def test_run_scenario_missing_file(self, tmp_path: Path) -> None:
        recorder = PocRecorder(Settings(output_dir=tmp_path))
        res = asyncio.run(recorder.run_scenario(RunScenarioParams(scenario=str(tmp_path / "missing.scenario.json"))))
        assert res.success is False
        assert res.error is not None
        assert "not found" in res.error

    def test_record_poc_schema_validation(self) -> None:
        params = RecordPocParams(
            url="http://localhost:47891",
            output_path="/tmp/demo_out",
            format="both",
            steps=[RecordingStep(action="wait", ms=500, caption="Step 1")],
        )
        assert params.format == "both"
        assert len(params.steps) == 1

    def test_create_server_registers_handlers(self) -> None:
        server = create_server()
        assert server.name == "poc-recorder"
