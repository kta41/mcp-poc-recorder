"""FFmpeg discovery and WebM-to-MP4/GIF transcoding helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Literal

from poc_recorder_mcp.types import ArtifactInfo


def resolve_ffmpeg_binary() -> str:
    """Locate system `ffmpeg` on PATH, falling back to `imageio-ffmpeg` static binary."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return str(exe)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "FFmpeg binary not found on PATH and `imageio-ffmpeg` fallback is unavailable. "
            "Install `ffmpeg` or run `uv sync` to install `imageio-ffmpeg`."
        ) from exc
    raise RuntimeError("FFmpeg binary could not be resolved.")


def transcode_to_mp4(
    webm_path: Path,
    mp4_path: Path,
    width: int = 1440,
    fps: int = 15,
    ffmpeg_bin: str | None = None,
) -> ArtifactInfo:
    """Convert a Playwright `.webm` recording to a widely compatible H.264 `.mp4`."""
    binary = ffmpeg_bin or resolve_ffmpeg_binary()
    mp4_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure width is divisible by 2 for yuv420p
    even_width = width if width % 2 == 0 else width - 1
    cmd = [
        binary,
        "-y",
        "-i",
        str(webm_path),
        "-vf",
        f"fps={fps},scale={even_width}:-2:flags=lanczos",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg MP4 conversion failed (exit {proc.returncode}): {proc.stderr[-600:]}")
    size = mp4_path.stat().st_size
    return ArtifactInfo(
        format="mp4",
        path=str(mp4_path.resolve()),
        size_bytes=size,
        size_kb=round(size / 1024.0, 2),
    )


def transcode_to_gif(
    webm_path: Path,
    gif_path: Path,
    width: int = 1280,
    fps: int = 15,
    ffmpeg_bin: str | None = None,
) -> ArtifactInfo:
    """Convert a Playwright `.webm` recording to a high-fidelity palette-optimized `.gif`."""
    binary = ffmpeg_bin or resolve_ffmpeg_binary()
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];"
        "[s0]palettegen=max_colors=256:stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    cmd = [
        binary,
        "-y",
        "-i",
        str(webm_path),
        "-vf",
        vf,
        "-loop",
        "0",
        str(gif_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg GIF conversion failed (exit {proc.returncode}): {proc.stderr[-600:]}")
    size = gif_path.stat().st_size
    return ArtifactInfo(
        format="gif",
        path=str(gif_path.resolve()),
        size_bytes=size,
        size_kb=round(size / 1024.0, 2),
    )


def convert_recording(
    webm_path: Path,
    base_output_path: Path,
    fmt: Literal["mp4", "gif", "both", "webm"],
    width: int = 1440,
    gif_width: int = 1280,
    fps: int = 15,
    ffmpeg_bin: str | None = None,
) -> list[ArtifactInfo]:
    """Produce requested output formats from a raw `.webm` recording."""
    artifacts: list[ArtifactInfo] = []
    stem_path = base_output_path.with_suffix("") if base_output_path.suffix.lower() in {".mp4", ".gif", ".webm"} else base_output_path

    if fmt == "webm":
        target = stem_path.with_suffix(".webm")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(webm_path, target)
        size = target.stat().st_size
        artifacts.append(
            ArtifactInfo(format="webm", path=str(target.resolve()), size_bytes=size, size_kb=round(size / 1024.0, 2))
        )
        return artifacts

    if fmt in {"mp4", "both"}:
        mp4_target = stem_path.with_suffix(".mp4")
        artifacts.append(transcode_to_mp4(webm_path, mp4_target, width=width, fps=fps, ffmpeg_bin=ffmpeg_bin))

    if fmt in {"gif", "both"}:
        gif_target = stem_path.with_suffix(".gif")
        artifacts.append(transcode_to_gif(webm_path, gif_target, width=gif_width, fps=fps, ffmpeg_bin=ffmpeg_bin))

    return artifacts
