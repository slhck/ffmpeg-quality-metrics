#!/usr/bin/env python3

import os
import sys
import json
from typing import cast


sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../"))

from ffmpeg_quality_metrics import VmafOptions  # noqa E402
from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm  # noqa E402

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")

with open(os.path.join(os.path.dirname(__file__), "response.json"), "r") as f:
    EXPECTED = json.load(f)


class TestMetrics:
    def test_all(self):
        run_ret_1 = ffqm(REF, DIST).calculate(metrics=["ssim"])
        run_ret_2 = ffqm(REF, DIST).calculate(metrics=["ssim", "psnr"])
        run_ret_3 = ffqm(REF, DIST).calculate(metrics=["ssim", "psnr", "vmaf"])

        assert len(run_ret_1) == 1
        assert len(run_ret_2) == 2
        assert len(run_ret_3) == 3

        for data in [run_ret_1, run_ret_2, run_ret_3]:
            for key, run_ret in data.items():
                self._test_frame_by_frame(EXPECTED[key], run_ret)

    def test_ssim(self):
        run_ret = ffqm(REF, DIST).calculate(["ssim"])["ssim"]
        self._test_frame_by_frame(EXPECTED["ssim"], run_ret)

    def test_psnr(self):
        run_ret = ffqm(REF, DIST).calculate(["psnr"])["psnr"]
        self._test_frame_by_frame(EXPECTED["psnr"], run_ret)

    def test_vmaf(self):
        vmaf_opts = {"model_path": "vmaf_v0.6.1.json"}
        run_ret = ffqm(REF, DIST).calculate(
            ["vmaf"], vmaf_options=cast(VmafOptions, vmaf_opts)
        )["vmaf"]
        self._test_frame_by_frame(EXPECTED["vmaf"], run_ret)

    def test_vif(self):
        run_ret = ffqm(REF, DIST).calculate(["vif"])["vif"]
        self._test_frame_by_frame(EXPECTED["vif"], run_ret)

    def _test_frame_by_frame(self, expected, run_ret):
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in expected_frame.keys():
                assert abs(expected_frame[key] - actual_frame[key]) < 0.02

    def test_global(self):
        f = ffqm(REF, DIST)
        f.calculate(metrics=["ssim", "psnr", "vmaf", "vif"])
        run_ret = f.get_global_stats()
        assert run_ret == EXPECTED["global"]
