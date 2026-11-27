"""Audio preparation for uploaded voice notes: convert to 16 kHz mono WAV, find pauses, and cut long notes at pauses
into pieces Sarvam's quick API accepts (at most 30 s). Cutting at a fixed time split "50 ... 50 piece" in the real
Hindi note (ADR-004), so cuts go in silences whenever there is one."""
from __future__ import annotations

import re
import shutil
import subprocess
import wave
from pathlib import Path

MIN_SECONDS = 0.5
MAX_SECONDS = 300.0


class AudioError(Exception):
    """The upload is not usable audio; the message is safe to show."""


def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise AudioError("ffmpeg is not installed") from e


def _seconds(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def to_wav16k(src: Path, dst: Path) -> float:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000",
                        "-sample_fmt", "s16", str(dst)], capture_output=True)
    if r.returncode != 0 or not dst.exists():
        raise AudioError("This file is not audio we can read")
    seconds = _seconds(dst)
    if seconds < MIN_SECONDS:
        raise AudioError("The recording is too short")
    if seconds > MAX_SECONDS:
        raise AudioError("The recording is longer than 5 minutes")
    return seconds


def silences(wav: Path) -> list[tuple[float, float]]:
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(wav), "-af", "silencedetect=noise=-30dB:d=0.35",
                        "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    total = _seconds(wav)
    return [(s, ends[i] if i < len(ends) else total) for i, s in enumerate(starts)]


def choose_cuts(duration: float, silences: list[tuple[float, float]], max_len: float = 28.0) -> list[float]:
    """Greedy: before each max_len boundary, cut at the middle of the last pause; with no pause, cut at the limit."""
    cuts: list[float] = []
    start = 0.0
    mids = [round((a + b) / 2, 3) for a, b in silences]
    while duration - start > max_len:
        limit = start + max_len
        inside = [m for m in mids if start < m <= limit]
        cut = inside[-1] if inside else round(limit, 3)
        cuts.append(cut)
        start = cut
    return cuts


def split(wav: Path, cuts: list[float], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    edges = [0.0, *cuts, None]
    parts = []
    for i in range(len(edges) - 1):
        part = out_dir / f"part{i}.wav"
        args = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav), "-ss", str(edges[i])]
        if edges[i + 1] is not None:
            args += ["-to", str(edges[i + 1])]
        subprocess.run([*args, "-c", "copy", str(part)], check=True, capture_output=True)
        parts.append(part)
    return parts
