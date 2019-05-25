#!/usr/bin/env python3
#
# Simple test suite

import os
import sys
import unittest
import subprocess

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/../'))

from ffmpeg_quality_metrics.__main__ import calc_ssim_psnr

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")


class TestMetrics(unittest.TestCase):
    def test_ssim(self):
        run_ret = calc_ssim_psnr(DIST, REF)["ssim"]
        self.assertEqual(run_ret, [{'n': 1, 'ssim_y': 0.936, 'ssim_u': 0.966, 'ssim_v': 0.951, 'ssim_avg': 0.951}, {'n': 2, 'ssim_y': 0.936, 'ssim_u': 0.966, 'ssim_v': 0.952, 'ssim_avg': 0.951}, {'n': 3, 'ssim_y': 0.935, 'ssim_u': 0.965, 'ssim_v': 0.952, 'ssim_avg': 0.951}])

    def test_psnr(self):
        run_ret = calc_ssim_psnr(DIST, REF)["psnr"]
        self.assertEqual(run_ret, [{'n': 1, 'mse_avg': 521.55, 'mse_y': 877.33, 'mse_u': 230.17, 'mse_v': 457.16, 'psnr_avg': 20.96, 'psnr_y': 18.7, 'psnr_u': 24.51, 'psnr_v': 21.53}, {'n': 2, 'mse_avg': 520.11, 'mse_y': 873.89, 'mse_u': 235.14, 'mse_v': 451.29, 'psnr_avg': 20.97, 'psnr_y': 18.72, 'psnr_u': 24.42, 'psnr_v': 21.59}, {'n': 3, 'mse_avg': 519.86, 'mse_y': 871.65, 'mse_u': 241.66, 'mse_v': 446.28, 'psnr_avg': 20.97, 'psnr_y': 18.73, 'psnr_u': 24.3, 'psnr_v': 21.63}])


if __name__ == '__main__':
    unittest.main()
