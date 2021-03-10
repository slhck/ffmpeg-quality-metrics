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
    "ssim": [
        {"n": 1, "ssim_y": 0.934, "ssim_u": 0.96, "ssim_v": 0.942, "ssim_avg": 0.945,},
        {"n": 2, "ssim_y": 0.934, "ssim_u": 0.96, "ssim_v": 0.943, "ssim_avg": 0.946,},
        {"n": 3, "ssim_y": 0.934, "ssim_u": 0.959, "ssim_v": 0.943, "ssim_avg": 0.945,},
    ],
    "vmaf": [
        {
            "psnr": 18.587308,
            "integer_motion2": 0.0,
            "integer_motion": 0.0,
            "ssim": 0.925976,
            "integer_adm2": 0.69907,
            "integer_adm_scale0": 0.708183,
            "integer_adm_scale1": 0.733469,
            "integer_adm_scale2": 0.718624,
            "integer_adm_scale3": 0.67301,
            "integer_vif_scale0": 0.539591,
            "integer_vif_scale1": 0.718022,
            "integer_vif_scale2": 0.751875,
            "integer_vif_scale3": 0.773503,
            "ms_ssim": 0.898265,
            "vmaf": 14.054853,
            "n": 1,
        },
        {
            "psnr": 18.60299,
            "integer_motion2": 0.359752,
            "integer_motion": 0.368929,
            "ssim": 0.926521,
            "integer_adm2": 0.698451,
            "integer_adm_scale0": 0.706706,
            "integer_adm_scale1": 0.73203,
            "integer_adm_scale2": 0.718262,
            "integer_adm_scale3": 0.672766,
            "integer_vif_scale0": 0.540231,
            "integer_vif_scale1": 0.719566,
            "integer_vif_scale2": 0.753567,
            "integer_vif_scale3": 0.775864,
            "ms_ssim": 0.899353,
            "vmaf": 14.464182,
            "n": 2,
        },
        {
            "psnr": 18.613101,
            "integer_motion2": 0.359752,
            "integer_motion": 0.359752,
            "ssim": 0.926481,
            "integer_adm2": 0.697126,
            "integer_adm_scale0": 0.706542,
            "integer_adm_scale1": 0.731351,
            "integer_adm_scale2": 0.716454,
            "integer_adm_scale3": 0.671197,
            "integer_vif_scale0": 0.539091,
            "integer_vif_scale1": 0.718657,
            "integer_vif_scale2": 0.753306,
            "integer_vif_scale3": 0.775984,
            "ms_ssim": 0.900086,
            "vmaf": 14.256442,
            "n": 3,
        },
    ],
    "psnr": [
        {
            "n": 1,
            "mse_avg": 536.71,
            "mse_y": 900.22,
            "mse_u": 234.48,
            "mse_v": 475.43,
            "psnr_avg": 20.83,
            "psnr_y": 18.59,
            "psnr_u": 24.43,
            "psnr_v": 21.36,
        },
        {
            "n": 2,
            "mse_avg": 535.29,
            "mse_y": 896.98,
            "mse_u": 239.4,
            "mse_v": 469.49,
            "psnr_avg": 20.84,
            "psnr_y": 18.6,
            "psnr_u": 24.34,
            "psnr_v": 21.41,
        },
        {
            "n": 3,
            "mse_avg": 535.04,
            "mse_y": 894.89,
            "mse_u": 245.8,
            "mse_v": 464.43,
            "psnr_avg": 20.85,
            "psnr_y": 18.61,
            "psnr_u": 24.22,
            "psnr_v": 21.46,
        },
    ],
    "vif": [
        {
            "n": 0,
            "scale_0": 0.263,
            "scale_1": 0.557,
            "scale_2": 0.624,
            "scale_3": 0.679,
        },
        {"n": 1, "scale_0": 0.264, "scale_1": 0.56, "scale_2": 0.627, "scale_3": 0.682},
        {
            "n": 2,
            "scale_0": 0.262,
            "scale_1": 0.559,
            "scale_2": 0.626,
            "scale_3": 0.683,
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
                "average": 20.84,
                "median": 20.84,
                "stdev": 0.008,
                "min": 20.83,
                "max": 20.85,
            },
        }
        self.assertEqual(run_ret, expected)


if __name__ == "__main__":
    unittest.main()
