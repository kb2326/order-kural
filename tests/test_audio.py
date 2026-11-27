import subprocess

import pytest

from app.audio import AudioError, choose_cuts, ffmpeg_exe, silences, split, to_wav16k


def make_wav(path, seconds_tone=1.0, seconds_silence=1.0, repeats=1):
    """Tone then silence, repeated, as a 16 kHz mono WAV made by ffmpeg."""
    parts = []
    for _ in range(repeats):
        parts += [f"sine=frequency=440:duration={seconds_tone}", f"anullsrc=r=16000:cl=mono:d={seconds_silence}"]
    inputs = sum((["-f", "lavfi", "-i", p] for p in parts), [])
    concat = "".join(f"[{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1"
    subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", *inputs, "-filter_complex", concat, "-ar", "16000",
                    "-ac", "1", str(path)], check=True)
    return path


def test_choose_cuts_prefers_silence():
    assert choose_cuts(35.8, [(17.6, 18.2)]) == [17.9]


def test_choose_cuts_hard_cut_without_silence():
    assert choose_cuts(60, []) == [28.0, 56.0]


def test_choose_cuts_short_audio():
    assert choose_cuts(12, [(3.0, 4.0)]) == []


def test_choose_cuts_uses_last_silence_before_limit():
    assert choose_cuts(50, [(5.0, 6.0), (20.0, 21.0), (30.0, 31.0)]) == [20.5, 30.5]


def test_to_wav16k_rejects_garbage(tmp_path):
    bad = tmp_path / "bad.ogg"
    bad.write_bytes(b"not audio")
    with pytest.raises(AudioError):
        to_wav16k(bad, tmp_path / "out.wav")


def test_to_wav16k_rejects_too_short(tmp_path):
    src = make_wav(tmp_path / "short.wav", seconds_tone=0.2, seconds_silence=0.1)
    with pytest.raises(AudioError, match="too short"):
        to_wav16k(src, tmp_path / "out.wav")


def test_to_wav16k_and_silences_and_split(tmp_path):
    src = make_wav(tmp_path / "in.wav", seconds_tone=1.0, seconds_silence=1.0, repeats=2)
    out = tmp_path / "out.wav"
    seconds = to_wav16k(src, out)
    assert 3.8 < seconds < 4.2
    gaps = silences(out)
    assert gaps and 0.9 < gaps[0][0] < 1.2
    pieces = split(out, [2.0], tmp_path / "parts")
    assert len(pieces) == 2 and all(p.exists() for p in pieces)
