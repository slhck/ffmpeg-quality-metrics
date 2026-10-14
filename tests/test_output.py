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


def _run_cli(*args):
    return subprocess.run(
        [
            "python3",
            "-m",
            "ffmpeg_quality_metrics",
            "tests/dist-854x480.mkv",
            "tests/ref-1280x720.mkv",
            "-m",
            "psnr",
            "ssim",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def test_summary_on_stderr():
    result = _run_cli()

    # stdout contains only the JSON output
    data = json.loads(result.stdout)
    assert "psnr" in data

    assert "Summary over 3 frames" in result.stderr
    assert "psnr_avg" in result.stderr
    assert "ssim_avg" in result.stderr
    assert "Summary" not in result.stdout


def test_no_summary():
    result = _run_cli("--no-summary")

    assert "Summary" not in result.stderr
    json.loads(result.stdout)


def test_invalid_ffmpeg_path():
    result = subprocess.run(
        [
            "python3",
            "-m",
            "ffmpeg_quality_metrics",
            "tests/dist-854x480.mkv",
            "tests/ref-1280x720.mkv",
            "--ffmpeg-path",
            "/nonexistent/ffmpeg",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert len(result.stderr.strip().splitlines()) == 1
    assert "Could not run ffmpeg at '/nonexistent/ffmpeg'" in result.stderr
