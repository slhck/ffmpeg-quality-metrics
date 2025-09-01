import os
import subprocess
import tempfile
import json


def test_output_file():
    with tempfile.NamedTemporaryFile(
        mode="w+", delete=False, suffix=".json"
    ) as tmp_file:
        output_file = tmp_file.name

    try:
        subprocess.check_call(
            [
                "python3",
                "-m",
                "ffmpeg_quality_metrics",
                "tests/dist-854x480.mkv",
                "tests/ref-1280x720.mkv",
                "-m",
                "psnr",
                "-o",
                output_file,
            ]
        )

        with open(output_file, "r") as f:
            data = json.load(f)

        assert "psnr" in data
        assert "global" in data
        assert len(data["psnr"]) > 0

    finally:
        if os.path.exists(output_file):
            os.remove(output_file)
