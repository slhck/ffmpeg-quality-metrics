#!/usr/bin/env python3
#
# Simple test suite

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))

from ffmpeg_quality_metrics.__main__ import calc_ssim_psnr, calculate_global_stats

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")


class TestMetrics(unittest.TestCase):
    def test_ssim(self):
        run_ret = calc_ssim_psnr(DIST, REF)["ssim"]
        expected = [{'n': 1, 'ssim_y': 0.936, 'ssim_u': 0.966, 'ssim_v': 0.951, 'ssim_avg': 0.951}, {'n': 2, 'ssim_y': 0.936, 'ssim_u': 0.966, 'ssim_v': 0.952, 'ssim_avg': 0.951}, {'n': 3, 'ssim_y': 0.935, 'ssim_u': 0.965, 'ssim_v': 0.952, 'ssim_avg': 0.951}]
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in ['ssim_y', 'ssim_u', 'ssim_v']:
                self.assertAlmostEqual(expected_frame[key], actual_frame[key], places=2)

    def test_psnr(self):
        run_ret = calc_ssim_psnr(DIST, REF)["psnr"]
        expected = [{"n": 1, "mse_avg": 527.49, "mse_y": 890.56, "mse_u": 229.48, "mse_v": 462.44, "psnr_avg": 20.91, "psnr_y": 18.63, "psnr_u": 24.52, "psnr_v": 21.48}, {"n": 2, "mse_avg": 526.02, "mse_y": 887.23, "mse_u": 234.41, "mse_v": 456.41, "psnr_avg": 20.92, "psnr_y": 18.65, "psnr_u": 24.43, "psnr_v": 21.54}, {"n": 3, "mse_avg": 525.82, "mse_y": 885.0, "mse_u": 240.96, "mse_v": 451.48, "psnr_avg": 20.92, "psnr_y": 18.66, "psnr_u": 24.31, "psnr_v": 21.58}]
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in ['mse_avg', 'mse_y', 'mse_u', 'mse_v', 'psnr_avg', 'psnr_y', 'psnr_u', 'psnr_v']:
                self.assertAlmostEqual(expected_frame[key], actual_frame[key], places=2)

    def test_global(self):
        run_ret = calculate_global_stats(calc_ssim_psnr(DIST, REF))
        expected = {"ssim": {"average": 0.952, "stdev": 0.0, "min": 0.952, "max": 0.952}, "psnr": {"average": 20.916666666666668, "stdev": 0.004714045207911053, "min": 20.91, "max": 20.92}}
        self.assertEqual(run_ret, expected)

if __name__ == '__main__':
    unittest.main()
