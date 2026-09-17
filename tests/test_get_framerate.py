#!/usr/bin/env python3

import os

import pytest

from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm
from ffmpeg_quality_metrics.ffmpeg_quality_metrics import FfmpegQualityMetricsError

REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")


class TestGetFramerate:
    def test_banner_path(self):
        # A normal file whose ffmpeg banner contains an "<n> fps" token is
        # parsed via the banner (the fallback is not needed).
        fps = ffqm.get_framerate(REF)
        assert fps == pytest.approx(25, abs=0.01)

    def test_ffprobe_fallback_when_banner_has_no_fps(self, monkeypatch):
        # Some container/codec combinations (e.g. FFV1 in .nut) make ffmpeg
        # print only "tbr"/"tbn" and no "<n> fps" token, so the banner regex
        # finds nothing. get_framerate must then fall back to ffprobe rather
        # than raising. We simulate the banner by stubbing run_command:
        #   - the ffmpeg -i call returns a banner without an fps token
        #   - the ffprobe call returns the exact rational rate
        import ffmpeg_quality_metrics.ffmpeg_quality_metrics as mod

        def fake_run_command(cmd, dry_run=False, allow_error=False):
            exe = os.path.basename(cmd[0])
            if exe.startswith("ffprobe"):
                # r_frame_rate query -> exact NTSC rational
                return ("30000/1001\n", "")
            # ffmpeg -i banner without an fps token (only tbr/tbn)
            return ("", "Stream #0:0: Video: ffv1, yuv420p, 320x240, 30 tbr, 240 tbn")

        monkeypatch.setattr(mod, "run_command", fake_run_command)

        fps = mod.FfmpegQualityMetrics.get_framerate("whatever.nut")
        assert fps == pytest.approx(30000 / 1001, abs=1e-6)

    def test_raises_when_no_rate_anywhere(self, monkeypatch):
        # If neither the banner nor ffprobe yields a usable rate, the original
        # error is still raised.
        import ffmpeg_quality_metrics.ffmpeg_quality_metrics as mod

        def fake_run_command(cmd, dry_run=False, allow_error=False):
            exe = os.path.basename(cmd[0])
            if exe.startswith("ffprobe"):
                return ("0/0\n", "")  # unusable
            return ("", "Stream #0:0: Video: ffv1, yuv420p, 320x240, 30 tbr")

        monkeypatch.setattr(mod, "run_command", fake_run_command)

        with pytest.raises(FfmpegQualityMetricsError):
            mod.FfmpegQualityMetrics.get_framerate("whatever.nut")
