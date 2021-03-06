#!/usr/bin/env python3
#
# Simple test suite

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))

from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm

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

    def test_vmaf(self):
        run_ret = ffqm(REF, DIST).calc_vmaf()
        expected = [{'psnr': 18.587308, 'integer_motion2': 0.0, 'integer_motion': 0.0, 'ssim': 0.925976, 'integer_adm2': 0.69907, 'integer_adm_scale0': 0.708183, 'integer_adm_scale1': 0.733469, 'integer_adm_scale2': 0.718624, 'integer_adm_scale3': 0.67301, 'integer_vif_scale0': 0.539591, 'integer_vif_scale1': 0.718022, 'integer_vif_scale2': 0.751875, 'integer_vif_scale3': 0.773503, 'ms_ssim': 0.898265, 'vmaf': 14.054853, 'n': 1}, {'psnr': 18.60299, 'integer_motion2': 0.359752, 'integer_motion': 0.368929, 'ssim': 0.926521, 'integer_adm2': 0.698451, 'integer_adm_scale0': 0.706706, 'integer_adm_scale1': 0.73203, 'integer_adm_scale2': 0.718262, 'integer_adm_scale3': 0.672766, 'integer_vif_scale0': 0.540231, 'integer_vif_scale1': 0.719566, 'integer_vif_scale2': 0.753567, 'integer_vif_scale3': 0.775864, 'ms_ssim': 0.899353, 'vmaf': 14.464182, 'n': 2}, {'psnr': 18.613101, 'integer_motion2': 0.359752, 'integer_motion': 0.359752, 'ssim': 0.926481, 'integer_adm2': 0.697126, 'integer_adm_scale0': 0.706542, 'integer_adm_scale1': 0.731351, 'integer_adm_scale2': 0.716454, 'integer_adm_scale3': 0.671197, 'integer_vif_scale0': 0.539091, 'integer_vif_scale1': 0.718657, 'integer_vif_scale2': 0.753306, 'integer_vif_scale3': 0.775984, 'ms_ssim': 0.900086, 'vmaf': 14.256442, 'n': 3}]
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in expected_frame.keys():
                self.assertAlmostEqual(expected_frame[key], actual_frame[key], places=2)

    def test_global(self):
        f = ffqm(REF, DIST)
        f.calc_ssim_psnr()
        run_ret = f.get_global_stats()
        expected = {'ssim': {'average': 0.945, 'median': 0.945, 'stdev': 0.0, 'min': 0.945, 'max': 0.946}, 'psnr': {'average': 20.84, 'median': 20.84, 'stdev': 0.008, 'min': 20.83, 'max': 20.85}}
        self.assertEqual(run_ret, expected)


if __name__ == '__main__':
    unittest.main()
