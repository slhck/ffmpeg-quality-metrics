# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

import logging
from platform import system as _current_os
from shutil import which
import os
import subprocess
import shlex

CUR_OS = _current_os()
IS_WIN = CUR_OS in ["Windows", "cli"]
IS_NIX = (not IS_WIN) and any(
    CUR_OS.startswith(i)
    for i in ["CYGWIN", "MSYS", "Linux", "Darwin", "SunOS", "FreeBSD", "NetBSD"]
)
NUL = "NUL" if IS_WIN else "/dev/null"

logger = logging.getLogger("ffmpeg-quality-metrics")


def win_path_check(path: str) -> str:
    """
    Format a file path correctly for Windows
    """
    if IS_WIN:
        return path.replace("\\", "/").replace(":", "\\:")
    return path


def win_vmaf_model_path_check(path: str) -> str:
    """
    Format vmaf model file path correctly for Windows
    """
    if IS_WIN:
        return win_path_check(path).replace("\\", "\\\\\\")
    return path


def has_brew():
    """
    Check if the user has Homebrew installed
    """
    return which("brew") is not None


def ffmpeg_is_from_brew():
    """
    Is the used ffmpeg from Homebrew?
    """
    ffmpeg_path = which("ffmpeg")
    if ffmpeg_path is None:
        return False

    return os.path.islink(ffmpeg_path) and "Cellar/ffmpeg" in os.readlink(ffmpeg_path)


def quoted_cmd(cmd):
    return " ".join([shlex.quote(c) for c in cmd])


def run_command(cmd, dry_run=False, allow_error=False):
    """
    Run a command directly
    """
    logger.debug(quoted_cmd(cmd))
    if dry_run:
        return "", ""

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if allow_error or process.returncode == 0:
        return stdout.decode("utf-8"), stderr.decode("utf-8")
    else:
        raise RuntimeError(
            f"error running command: {quoted_cmd(cmd)}\n{stdout.decode('utf-8')}\n{stderr.decode('utf-8')}"
        )
