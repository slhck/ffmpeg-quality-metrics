#!/usr/bin/env python3
#
# Simple test suite

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))

from ffmpeg_quality_metrics.ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")


class TestMetrics(unittest.TestCase):
    def test_ssim(self):
        run_ret = ffqm(REF, DIST).calc_ssim_psnr()["ssim"]
        expected = [{'n': 1, 'ssim_y': 0.934, 'ssim_u': 0.96, 'ssim_v': 0.942, 'ssim_avg': 0.945}, {'n': 2, 'ssim_y': 0.934, 'ssim_u': 0.96, 'ssim_v': 0.943, 'ssim_avg': 0.946}, {'n': 3, 'ssim_y': 0.934, 'ssim_u': 0.959, 'ssim_v': 0.943, 'ssim_avg': 0.945}]
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in ['ssim_y', 'ssim_u', 'ssim_v']:
                self.assertAlmostEqual(expected_frame[key], actual_frame[key], places=2)

    def test_psnr(self):
        run_ret = ffqm(REF, DIST).calc_ssim_psnr()["psnr"]
        expected = [{'n': 1, 'mse_avg': 536.71, 'mse_y': 900.22, 'mse_u': 234.48, 'mse_v': 475.43, 'psnr_avg': 20.83, 'psnr_y': 18.59, 'psnr_u': 24.43, 'psnr_v': 21.36}, {'n': 2, 'mse_avg': 535.29, 'mse_y': 896.98, 'mse_u': 239.4, 'mse_v': 469.49, 'psnr_avg': 20.84, 'psnr_y': 18.6, 'psnr_u': 24.34, 'psnr_v': 21.41}, {'n': 3, 'mse_avg': 535.04, 'mse_y': 894.89, 'mse_u': 245.8, 'mse_v': 464.43, 'psnr_avg': 20.85, 'psnr_y': 18.61, 'psnr_u': 24.22, 'psnr_v': 21.46}]
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in ['mse_avg', 'mse_y', 'mse_u', 'mse_v', 'psnr_avg', 'psnr_y', 'psnr_u', 'psnr_v']:
                self.assertAlmostEqual(expected_frame[key], actual_frame[key], places=2)

    def test_global(self):
        f = ffqm(REF, DIST)
        f.calc_ssim_psnr()
        run_ret = f.get_global_stats()
        expected = {'ssim': {'average': 0.945, 'median': 0.945, 'stdev': 0.0, 'min': 0.945, 'max': 0.946}, 'psnr': {'average': 20.84, 'median': 20.84, 'stdev': 0.008, 'min': 20.83, 'max': 20.85}}
        self.assertEqual(run_ret, expected)


if __name__ == '__main__':
    unittest.main()
