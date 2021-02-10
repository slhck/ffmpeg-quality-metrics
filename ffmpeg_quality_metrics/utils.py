# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

from platform import system as _current_os
from shutil import which
import os
import sys
import subprocess
import shlex

CUR_OS = _current_os()
IS_WIN = CUR_OS in ["Windows", "cli"]
IS_NIX = (not IS_WIN) and any(
    CUR_OS.startswith(i)
    for i in ["CYGWIN", "MSYS", "Linux", "Darwin", "SunOS", "FreeBSD", "NetBSD"]
)
NUL = "NUL" if IS_WIN else "/dev/null"


def win_path_check(path):
    """
    Format a file path correctly for Windows
    """
    if IS_WIN:
        return path.replace("\\", "/").replace(":", "\\:")
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


def print_error(msg):
    print("ERROR: %s" % msg, file=sys.stderr)


def print_warning(msg):
    print("WARNING: %s" % msg, file=sys.stderr)


def print_info(msg):
    print("INFO: %s" % msg, file=sys.stderr)


def quoted_cmd(cmd):
    return " ".join([shlex.quote(c) for c in cmd])


def run_command(cmd, dry_run=False, verbose=False, allow_error=False):
    """
    Run a command directly
    """
    if dry_run or verbose:
        print_info(quoted_cmd(cmd))
        if dry_run:
            return

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if allow_error or process.returncode == 0:
        return stdout.decode("utf-8"), stderr.decode("utf-8")
    else:
        raise RuntimeError(
            f"error running command: {quoted_cmd(cmd)}\n{stderr.decode('utf-8')}"
        )
