#!/usr/bin/env python3

import csv
import json
import os
from io import StringIO
from typing import cast

from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm
from ffmpeg_quality_metrics import VmafOptions

DIST = os.path.join(os.path.dirname(__file__), "dist-854x480.mkv")
REF = os.path.join(os.path.dirname(__file__), "ref-1280x720.mkv")

# generate with:
# python3 -m ffmpeg_quality_metrics test/dist-854x480.mkv test/ref-1280x720.mkv -m ssim psnr vmaf vif > test/response.json
with open(os.path.join(os.path.dirname(__file__), "response.json"), "r") as f:
    EXPECTED = json.load(f)
GLOBAL = EXPECTED["global"]

THRESHOLD = 0.25  # we need some threshold here because exact reproductions are not guaranteed across platforms


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

    def test_vmaf_features(self):
        vmaf_opts = {
            "features": [
                "cambi",
                "ciede",
                "vif",
                "adm",
                "motion",
                "float_ssim",
                "float_ms_ssim",
            ]
        }
        run_ret = ffqm(REF, DIST).calculate(
            ["vmaf"], vmaf_options=cast(VmafOptions, vmaf_opts)
        )["vmaf"]

        assert list(run_ret[0].keys()) == [
            "integer_adm2",
            "integer_adm_scale0",
            "integer_adm_scale1",
            "integer_adm_scale2",
            "integer_adm_scale3",
            "integer_motion2",
            "integer_motion",
            "integer_vif_scale0",
            "integer_vif_scale1",
            "integer_vif_scale2",
            "integer_vif_scale3",
            "cambi",
            "ciede2000",
            "float_ssim",
            "float_ms_ssim",
            "vmaf",
            "n",
        ]

    def test_vmaf_feature_options(self):
        vmaf_opts = {
            "features": [
                "cambi:full_ref=true",
            ]
        }
        run_ret = ffqm(REF, DIST).calculate(
            ["vmaf"], vmaf_options=cast(VmafOptions, vmaf_opts)
        )["vmaf"]

        assert list(run_ret[0].keys()) == [
            "integer_adm2",
            "integer_adm_scale0",
            "integer_adm_scale1",
            "integer_adm_scale2",
            "integer_adm_scale3",
            "integer_motion2",
            "integer_motion",
            "integer_vif_scale0",
            "integer_vif_scale1",
            "integer_vif_scale2",
            "integer_vif_scale3",
            "cambi",
            "cambi_source",
            "cambi_full_reference",
            "vmaf",
            "n",
        ]

    def test_vif(self):
        run_ret = ffqm(REF, DIST).calculate(["vif"])["vif"]
        self._test_frame_by_frame(EXPECTED["vif"], run_ret)

    def _test_frame_by_frame(self, expected, run_ret):
        for expected_frame, actual_frame in zip(expected, run_ret):
            for key in expected_frame.keys():
                assert abs(expected_frame[key] - actual_frame[key]) < THRESHOLD

    def test_global(self):
        f = ffqm(REF, DIST)
        f.calculate(metrics=["ssim", "psnr", "vmaf", "vif"])
        run_ret = f.get_global_stats()
        for key in GLOBAL.keys():
            for subkey in GLOBAL[key].keys():
                print(key, subkey)
                for metric in GLOBAL[key][subkey].keys():
                    assert (
                        abs(GLOBAL[key][subkey][metric] - run_ret[key][subkey][metric])
                        < THRESHOLD
                    )

    def test_csv_output(self):
        f = ffqm(REF, DIST)
        f.calculate(metrics=["ssim", "psnr"])
        csv_output = f.get_results_csv()

        # Check that CSV output is not empty
        assert csv_output.strip() != ""

        # Parse CSV properly using csv module
        csv_reader = csv.reader(StringIO(csv_output))
        rows = list(csv_reader)

        assert len(rows) > 0, "CSV should have at least a header row"
        headers = rows[0]

        # Verify expected columns exist
        expected_columns = [
            "n",
            "mse_avg",
            "mse_y",
            "mse_u",
            "mse_v",
            "psnr_avg",
            "psnr_y",
            "psnr_u",
            "psnr_v",
            "ssim_y",
            "ssim_u",
            "ssim_v",
            "ssim_avg",
            "input_file_dist",
            "input_file_ref",
        ]

        for col in expected_columns:
            assert col in headers, (
                f"Expected column '{col}' not found in CSV headers: {headers}"
            )

        # Check that we have data rows (at least 2 rows: header + data)
        assert len(rows) > 1, "CSV should contain header and at least one data row"

        # Verify data rows have correct number of columns
        for i, row in enumerate(rows[1:], 1):
            assert len(row) == len(headers), (
                f"Row {i} has {len(row)} values but expected {len(headers)}"
            )

            # Check that frame number (n) is numeric and starts from 1
            frame_num = int(row[headers.index("n")])
            assert frame_num == i, f"Frame number should be {i} but got {frame_num}"

            # Verify input file columns contain the correct file paths
            dist_col_idx = headers.index("input_file_dist")
            ref_col_idx = headers.index("input_file_ref")
            assert DIST in row[dist_col_idx], f"Expected distorted file path in row {i}"
            assert REF in row[ref_col_idx], f"Expected reference file path in row {i}"

    def test_num_frames(self):
        # Test with 2 frames (less than available)
        f = ffqm(REF, DIST, num_frames=2)
        f.calculate(metrics=["ssim", "psnr"])

        # Check that we only have 2 frames
        assert len(f.data["ssim"]) == 2
        assert len(f.data["psnr"]) == 2

        # Check that frame numbers are 1-2
        for i, frame in enumerate(f.data["ssim"], 1):
            assert frame["n"] == i

        # Test with 1 frame
        f = ffqm(REF, DIST, num_frames=1)
        f.calculate(metrics=["psnr"])

        assert len(f.data["psnr"]) == 1
        assert f.data["psnr"][0]["n"] == 1

        # Test with more frames than available (should return all available frames)
        f = ffqm(REF, DIST, num_frames=10)
        f.calculate(metrics=["psnr"])

        # Test videos have 3 frames, so even when asking for 10, we get 3
        assert len(f.data["psnr"]) == 3

        # Check that all frames are processed when num_frames is not specified
        f = ffqm(REF, DIST)
        f.calculate(metrics=["psnr"])

        # The test videos have 3 frames
        assert len(f.data["psnr"]) == 3

    def test_start_offset_timestamp(self):
        # Test with timestamp-based seeking (seek to 0.04s, which is frame 2 at 25fps)
        f = ffqm(REF, DIST, start_offset="0.04")
        f.calculate(metrics=["psnr"])

        # Should get 2 frames (frames 2 and 3)
        assert len(f.data["psnr"]) == 2

        # Frame numbers in output should still be sequential starting from 1
        # (ffmpeg resets frame numbering after seeking)
        for i, frame in enumerate(f.data["psnr"], 1):
            assert frame["n"] == i

    def test_start_offset_frame(self):
        # Test with frame-based seeking (seek to frame 1, which is 0.04s at 25fps)
        f = ffqm(REF, DIST, start_offset="f:1")
        f.calculate(metrics=["psnr"])

        # Should get 2 frames (frames 2 and 3 from original)
        assert len(f.data["psnr"]) == 2

    def test_start_offset_with_num_frames(self):
        # Test combining start_offset with num_frames
        f = ffqm(REF, DIST, start_offset="0.04", num_frames=1)
        f.calculate(metrics=["psnr"])

        # Should get only 1 frame
        assert len(f.data["psnr"]) == 1
