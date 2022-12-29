# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

import logging
import os
import shlex
import subprocess
from platform import system
from shutil import which
from typing import List, Tuple

IS_WIN = system() in ["Windows", "cli"]
NUL = "NUL" if IS_WIN else "/dev/null"

logger = logging.getLogger("ffmpeg-quality-metrics")


def win_path_check(path: str) -> str:
    """
    Format a file path correctly for Windows

    Args:
        path (str): The path to format

    Returns:
        str: The formatted path
    """
    if IS_WIN:
        return path.replace("\\", "/").replace(":", "\\:")
    return path


def win_vmaf_model_path_check(path: str) -> str:
    """
    Format vmaf model file path correctly for Windows

    Args:
        path (str): The path to format

    Returns:
        str: The formatted path
    """
    if IS_WIN:
        return win_path_check(path).replace("\\", "\\\\\\")
    return path


def has_brew() -> bool:
    """
    Check if the user has Homebrew installed

    Returns:
        bool: True if Homebrew is installed, False otherwise
    """
    return which("brew") is not None


def ffmpeg_is_from_brew() -> bool:
    """
    Is the used ffmpeg from Homebrew?

    Returns:
        bool: True if ffmpeg is from Homebrew, False otherwise
    """
    ffmpeg_path = which("ffmpeg")
    if ffmpeg_path is None:
        return False

    return os.path.islink(ffmpeg_path) and "Cellar/ffmpeg" in os.readlink(ffmpeg_path)


def quoted_cmd(cmd: List[str]) -> str:
    """
    Quote a command for printing.

    Args:
        cmd (list): The command to quote

    Returns:
        str: The quoted command
    """
    return " ".join([shlex.quote(c) for c in cmd])


def run_command(
    cmd, dry_run: bool = False, allow_error: bool = False
) -> Tuple[str, str]:
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
