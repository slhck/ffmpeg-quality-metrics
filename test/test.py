#!/usr/bin/env python3
#
# Simple test suite

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../"))

from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm  # noqa E402

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")

EXPECTED = {
    "vmaf": [
        {
            "psnr": 18.586972,
            "integer_motion2": 0.0,
            "integer_motion": 0.0,
            "ssim": 0.925976,
            "integer_adm2": 0.699075,
            "integer_adm_scale0": 0.708874,
            "integer_adm_scale1": 0.733523,
            "integer_adm_scale2": 0.718368,
            "integer_adm_scale3": 0.672973,
            "integer_vif_scale0": 0.53943,
            "integer_vif_scale1": 0.717914,
            "integer_vif_scale2": 0.751785,
            "integer_vif_scale3": 0.77342,
            "ms_ssim": 0.898255,
            "vmaf": 14.051072,
            "n": 1,
        },
        {
            "psnr": 18.602698,
            "integer_motion2": 0.359752,
            "integer_motion": 0.368929,
            "ssim": 0.926521,
            "integer_adm2": 0.698627,
            "integer_adm_scale0": 0.70731,
            "integer_adm_scale1": 0.732094,
            "integer_adm_scale2": 0.718446,
            "integer_adm_scale3": 0.672873,
            "integer_vif_scale0": 0.540013,
            "integer_vif_scale1": 0.719462,
            "integer_vif_scale2": 0.753449,
            "integer_vif_scale3": 0.775636,
            "ms_ssim": 0.899347,
            "vmaf": 14.480823,
            "n": 2,
        },
        {
            "psnr": 18.612721,
            "integer_motion2": 0.359752,
            "integer_motion": 0.359752,
            "ssim": 0.926476,
            "integer_adm2": 0.697117,
            "integer_adm_scale0": 0.706941,
            "integer_adm_scale1": 0.731659,
            "integer_adm_scale2": 0.716069,
            "integer_adm_scale3": 0.671182,
            "integer_vif_scale0": 0.538908,
            "integer_vif_scale1": 0.718575,
            "integer_vif_scale2": 0.753169,
            "integer_vif_scale3": 0.775781,
            "ms_ssim": 0.90007,
            "vmaf": 14.241643,
            "n": 3,
        },
    ],
    "psnr": [
        {
            "n": 1,
            "mse_avg": 536.66,
            "mse_y": 900.29,
            "mse_u": 234.46,
            "mse_v": 475.24,
            "psnr_avg": 20.83,
            "psnr_y": 18.59,
            "psnr_u": 24.43,
            "psnr_v": 21.36,
        },
        {
            "n": 2,
            "mse_avg": 535.24,
            "mse_y": 897.04,
            "mse_u": 239.35,
            "mse_v": 469.35,
            "psnr_avg": 20.85,
            "psnr_y": 18.6,
            "psnr_u": 24.34,
            "psnr_v": 21.42,
        },
        {
            "n": 3,
            "mse_avg": 534.98,
            "mse_y": 894.97,
            "mse_u": 245.74,
            "mse_v": 464.21,
            "psnr_avg": 20.85,
            "psnr_y": 18.61,
            "psnr_u": 24.23,
            "psnr_v": 21.46,
        },
    ],
    "ssim": [
        {"n": 1, "ssim_y": 0.934, "ssim_u": 0.96, "ssim_v": 0.942, "ssim_avg": 0.945},
        {"n": 2, "ssim_y": 0.934, "ssim_u": 0.96, "ssim_v": 0.943, "ssim_avg": 0.946},
        {"n": 3, "ssim_y": 0.934, "ssim_u": 0.959, "ssim_v": 0.943, "ssim_avg": 0.945},
    ],
    "vif": [
        {
            "n": 0,
            "scale_0": 0.262,
            "scale_1": 0.557,
            "scale_2": 0.624,
            "scale_3": 0.679,
        },
        {"n": 1, "scale_0": 0.263, "scale_1": 0.56, "scale_2": 0.626, "scale_3": 0.682},
        {
            "n": 2,
            "scale_0": 0.262,
            "scale_1": 0.559,
            "scale_2": 0.626,
            "scale_3": 0.682,
        },
    ],
}


class TestMetrics(unittest.TestCase):
    def test_all(self):
        run_ret_1 = ffqm(REF, DIST).calc(metrics=["ssim"])
        run_ret_2 = ffqm(REF, DIST).calc(metrics=["ssim", "psnr"])
        run_ret_3 = ffqm(REF, DIST).calc(metrics=["ssim", "psnr", "vmaf"])

        assert len(run_ret_1) == 1
        assert len(run_ret_2) == 2
        assert len(run_ret_3) == 3

        for data in [run_ret_1, run_ret_2, run_ret_3]:
            for key, run_ret in data.items():
                self._test_frame_by_frame(EXPECTED[key], run_ret)

    def test_ssim(self):
        run_ret = ffqm(REF, DIST).calc(["ssim"])["ssim"]
        self._test_frame_by_frame(EXPECTED["ssim"], run_ret)

    def test_psnr(self):
        run_ret = ffqm(REF, DIST).calc(["psnr"])["psnr"]
        self._test_frame_by_frame(EXPECTED["psnr"], run_ret)

    def test_vmaf_legacy(self):
        run_ret = ffqm(REF, DIST).calc_vmaf(model_path="vmaf_v0.6.1.json")
        self._test_frame_by_frame(EXPECTED["vmaf"], run_ret)

    def test_vmaf(self):
        run_ret = ffqm(REF, DIST).calc(
            ["vmaf"], vmaf_options={"model_path": "vmaf_v0.6.1.json"}
        )["vmaf"]
        self._test_frame_by_frame(EXPECTED["vmaf"], run_ret)

    def test_vif(self):
        run_ret = ffqm(REF, DIST).calc(["vif"])["vif"]
        self._test_frame_by_frame(EXPECTED["vif"], run_ret)

    def _test_frame_by_frame(self, expected, run_ret):
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in expected_frame.keys():
                self.assertAlmostEqual(expected_frame[key], actual_frame[key], places=2)

    def test_global(self):
        f = ffqm(REF, DIST)
        f.calc()
        run_ret = f.get_global_stats()
        expected = {
            "ssim": {
                "average": 0.945,
                "median": 0.945,
                "stdev": 0.0,
                "min": 0.945,
                "max": 0.946,
            },
            "psnr": {
                "average": 20.843,
                "median": 20.85,
                "stdev": 0.009,
                "min": 20.83,
                "max": 20.85,
            },
        }
        self.assertEqual(run_ret, expected)


if __name__ == "__main__":
    unittest.main()
