#!/usr/bin/env python3

import logging
import os
import subprocess

import pytest

import ffmpeg_quality_metrics.ffmpeg_quality_metrics as mod
from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm
from ffmpeg_quality_metrics import FfmpegQualityMetricsError

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")


def _make_clip(path, size="320x240", rate=25, duration=1.0):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate={rate}:duration={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return str(path)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    """
    Short clips with different properties, keyed by name.
    """
    tmp = tmp_path_factory.mktemp("check_inputs")
    audio = os.path.join(tmp, "audio.m4a")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc",
            "-t",
            "1",
            audio,
        ],
        check=True,
    )
    garbage = os.path.join(tmp, "garbage.mp4")
    with open(garbage, "w") as f:
        f.write("not a video")

    return {
        "base": _make_clip(tmp / "base.mp4"),
        "base_mkv": _make_clip(tmp / "base.mkv"),
        "fps30": _make_clip(tmp / "fps30.mp4", rate=30),
        "long": _make_clip(tmp / "long.mp4", duration=2.0),
        "long_mkv": _make_clip(tmp / "long.mkv", duration=2.0),
        "audio": audio,
        "garbage": garbage,
    }


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


class TestProbeInput:
    def test_probe(self):
        info = ffqm.probe_input(REF)
        assert info["path"] == REF
        assert (info["width"], info["height"]) == (1280, 720)
        assert info["framerate"] == pytest.approx(25)
        assert info["duration"] == pytest.approx(0.12)

    def test_frame_count(self, clips):
        assert ffqm.probe_input(clips["long"])["nb_frames"] == 50

    def test_missing_file(self):
        with pytest.raises(FfmpegQualityMetricsError, match="File not found"):
            ffqm.probe_input("does-not-exist.mp4")

    def test_no_video_stream(self, clips):
        with pytest.raises(FfmpegQualityMetricsError, match="No video stream"):
            ffqm.probe_input(clips["audio"])

    def test_unreadable_file(self, clips):
        with pytest.raises(FfmpegQualityMetricsError, match="Could not read file"):
            ffqm.probe_input(clips["garbage"])


class TestCheckInputs:
    def test_resolution_mismatch(self, caplog):
        ref_info, dist_info = ffqm(REF, DIST).check_inputs()  # type: ignore[misc]
        assert (dist_info["width"], dist_info["height"]) == (854, 480)

        warnings = _warnings(caplog)
        assert len(warnings) == 1
        assert (
            "Resolutions differ: distorted 854x480, reference 1280x720" in (warnings[0])
        )
        assert "scaled to 1280x720 (bicubic)" in warnings[0]

    def test_matching_inputs(self, clips, caplog):
        assert ffqm(clips["base"], clips["base"]).check_inputs() is not None
        assert not any("differ" in w for w in _warnings(caplog))

    def test_framerate_mismatch(self, clips, caplog):
        ffqm(clips["base"], clips["fps30"]).check_inputs()
        warnings = _warnings(caplog)
        assert any(
            "Frame rates differ: distorted 30 fps, reference 25 fps" in w
            for w in warnings
        )

    def test_forced_framerate(self, clips, caplog):
        ffqm(clips["base"], clips["fps30"], framerate=25).check_inputs()
        assert not any("Frame rates differ" in w for w in _warnings(caplog))

    def test_frame_count_mismatch(self, clips, caplog):
        ffqm(clips["base"], clips["long"]).check_inputs()
        warnings = _warnings(caplog)
        assert any(
            "Frame counts differ: distorted 50, reference 25" in w for w in warnings
        )
        assert any("remaining frames of the distorted video" in w for w in warnings)

    def test_duration_mismatch(self, clips, caplog):
        # Matroska has no frame count, so durations are compared
        ffqm(clips["long_mkv"], clips["base_mkv"]).check_inputs()
        warnings = _warnings(caplog)
        assert any(
            "Durations differ: distorted 1.000 s, reference 2.000 s" in w
            for w in warnings
        )

    def test_duration_with_dist_delay(self, clips, caplog):
        # trimming 1 s from the 2 s reference leaves the same duration as the distorted clip
        ffqm(clips["long"], clips["base"], dist_delay=1.0).check_inputs()
        assert not any("differ" in w for w in _warnings(caplog))

    def test_duration_with_num_frames(self, clips, caplog):
        ffqm(clips["long"], clips["base"], num_frames=10).check_inputs()
        assert not any("differ" in w for w in _warnings(caplog))

    def test_ffprobe_missing(self, monkeypatch, caplog):
        monkeypatch.setattr(
            mod, "get_ffprobe_path", lambda ffmpeg_path: "/nonexistent/ffprobe"
        )
        f = ffqm(REF, DIST)
        assert f.check_inputs() is None
        assert any("ffprobe not found" in w for w in _warnings(caplog))

        # the calculation still works, and the frame rate check falls back to ffmpeg
        assert len(f.calculate(["psnr"])["psnr"]) == 3

    def test_calculate_checks_inputs_once(self, monkeypatch):
        f = ffqm(REF, DIST)
        calls = []
        original = f.check_inputs

        def counting_check_inputs():
            calls.append(1)
            return original()

        monkeypatch.setattr(f, "check_inputs", counting_check_inputs)
        f.calculate(["psnr"])
        f.calculate(["ssim"])
        assert len(calls) == 1
        assert f.input_info is not None

    def test_calculate_fails_without_video_stream(self, clips):
        f = ffqm(REF, clips["audio"])
        with pytest.raises(FfmpegQualityMetricsError, match="No video stream"):
            f.calculate(["psnr"])


def test_cli_error_without_traceback(clips):
    result = subprocess.run(
        ["python3", "-m", "ffmpeg_quality_metrics", clips["audio"], REF],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "No video stream found" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
