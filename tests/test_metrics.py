#!/usr/bin/env python3

import csv
import json
import os
import subprocess
from io import StringIO
from typing import cast

import pytest

from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm
from ffmpeg_quality_metrics import VmafOptions
from ffmpeg_quality_metrics.ffmpeg_quality_metrics import FfmpegQualityMetricsError

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

    def test_vmaf_v1(self):
        vmaf_opts = {"model_path": "vmaf_v1.0.16_3d0h.json", "ten_bit": True}
        try:
            run_ret = ffqm(REF, DIST).calculate(
                ["vmaf"], vmaf_options=cast(VmafOptions, vmaf_opts)
            )["vmaf"]
        except FfmpegQualityMetricsError as e:
            if "libvmaf version" in str(e):
                pytest.skip("libvmaf version does not support VMAF v1 models")
            raise

        assert len(run_ret) == 3
        for frame in run_ret:
            assert 0 <= frame["vmaf"] <= 100
            # v1 models use CAMBI and speed_chroma features
            assert any(key.startswith("cambi") for key in frame.keys())
            assert any(key.startswith("speed_chroma") for key in frame.keys())

    def test_vmaf_10bit(self):
        vmaf_opts = {"model_path": "vmaf_v0.6.1.json", "ten_bit": True}
        run_ret = ffqm(REF, DIST).calculate(
            ["vmaf"], vmaf_options=cast(VmafOptions, vmaf_opts)
        )["vmaf"]

        # 8-to-10-bit conversion is lossless, so scores should be close to the 8-bit baseline
        for expected_frame, actual_frame in zip(EXPECTED["vmaf"], run_ret):
            assert abs(expected_frame["vmaf"] - actual_frame["vmaf"]) < 1.0

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

        # the exact set of core feature keys depends on the libvmaf version,
        # so only check for the explicitly requested features
        for key in [
            "cambi",
            "ciede2000",
            "float_ssim",
            "float_ms_ssim",
            "integer_adm2",
            "integer_motion2",
            "integer_vif_scale0",
            "vmaf",
            "n",
        ]:
            assert key in run_ret[0]

    def test_vmaf_feature_options(self):
        vmaf_opts = {
            "features": [
                "cambi:full_ref=true",
            ]
        }
        run_ret = ffqm(REF, DIST).calculate(
            ["vmaf"], vmaf_options=cast(VmafOptions, vmaf_opts)
        )["vmaf"]

        for key in [
            "cambi",
            "cambi_source",
            "cambi_full_reference",
            "vmaf",
            "n",
        ]:
            assert key in run_ret[0]

    def test_vif(self):
        run_ret = ffqm(REF, DIST).calculate(["vif"])["vif"]
        self._test_frame_by_frame(EXPECTED["vif"], run_ret)

    def _test_frame_by_frame(self, expected, run_ret):
        for expected_frame, actual_frame in zip(expected, run_ret):
            # only compare keys present in both, as the exact set of VMAF submetrics
            # depends on the libvmaf version
            common_keys = set(expected_frame.keys()) & set(actual_frame.keys())
            assert "n" in common_keys and len(common_keys) > 1
            for key in common_keys:
                assert abs(expected_frame[key] - actual_frame[key]) < THRESHOLD

    def test_global(self):
        f = ffqm(REF, DIST)
        f.calculate(metrics=["ssim", "psnr", "vmaf", "vif"])
        run_ret = f.get_global_stats()
        for key in GLOBAL.keys():
            for subkey in GLOBAL[key].keys():
                if subkey not in run_ret[key]:
                    # the exact set of VMAF submetrics depends on the libvmaf version
                    continue
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

    def test_dist_delay_aligns_streams(self, misaligned_clips):
        # The distorted clip is the reference content starting DELAY seconds in,
        # re-encoded at a lower bitrate. Without alignment the frames are paired
        # out of order and VMAF is low; with the correct dist_delay the streams
        # are aligned by trimming the reference's leading frames and VMAF is high.
        ref, dist, delay = misaligned_clips

        unaligned_vmaf = ffqm(ref, dist, framerate=30, dist_delay=0)
        unaligned_vmaf.calculate(metrics=["vmaf"])
        aligned_vmaf = ffqm(ref, dist, framerate=30, dist_delay=delay)
        aligned_vmaf.calculate(metrics=["vmaf"])

        unaligned_score = unaligned_vmaf.get_global_stats()["vmaf"]["vmaf"][
            "average"
        ]
        aligned_score = aligned_vmaf.get_global_stats()["vmaf"]["vmaf"]["average"]

        # The aligned reference still contains one second more content than the
        # distorted clip. libvmaf must stop at the end of the shorter stream
        # rather than repeat the distorted clip's final frame against that tail.
        assert len(aligned_vmaf.data["vmaf"]) == 90

        # Alignment must raise VMAF substantially (regression guard: a broken
        # dist_delay leaves the score unchanged).
        assert aligned_score > unaligned_score + 20, (
            f"dist_delay did not align streams: unaligned={unaligned_score:.2f}, "
            f"aligned={aligned_score:.2f}"
        )

    def test_dist_delay_matches_manual_trim(self, misaligned_clips):
        # A positive dist_delay must produce the same result as physically
        # trimming the reference's leading frames by hand.
        ref, dist, delay = misaligned_clips

        via_param = ffqm(ref, dist, framerate=30, dist_delay=delay)
        via_param.calculate(metrics=["vmaf"])
        param_score = via_param.get_global_stats()["vmaf"]["vmaf"]["average"]

        trimmed_ref = os.path.join(os.path.dirname(dist), "ref_trimmed.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", str(delay), "-i", ref, "-c:v", "libx264", "-qp", "0",
                "-pix_fmt", "yuv420p", trimmed_ref,
            ],
            check=True,
        )
        via_trim = ffqm(trimmed_ref, dist, framerate=30)
        via_trim.calculate(metrics=["vmaf"])
        trim_score = via_trim.get_global_stats()["vmaf"]["vmaf"]["average"]

        assert via_param.dist_delay == delay
        assert abs(param_score - trim_score) < 2.0, (
            f"dist_delay result {param_score:.2f} differs from manual trim "
            f"{trim_score:.2f}"
        )


@pytest.fixture(scope="module")
def misaligned_clips(tmp_path_factory):
    """
    Build a reference clip and a 'distorted' clip that emulates a capture which
    started `DELAY` seconds late: it is the reference content from `DELAY`
    onwards, re-encoded at a lower bitrate. Yields (ref_path, dist_path, delay).
    """
    delay = 2.0
    tmp = tmp_path_factory.mktemp("dist_delay")
    ref = os.path.join(tmp, "ref.mp4")
    dist = os.path.join(tmp, "dist.mp4")

    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=6",
            "-c:v", "libx264", "-qp", "10", "-pix_fmt", "yuv420p", ref,
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(delay), "-i", ref, "-t", "3",
            "-c:v", "libx264", "-b:v", "1500k", "-pix_fmt", "yuv420p", dist,
        ],
        check=True,
    )
    return ref, dist, delay
