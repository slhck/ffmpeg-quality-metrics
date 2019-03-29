#!/usr/bin/env python3
#
# Author: Werner Robitza

import argparse
import os
import sys
import re

sys.path.append(os.path.dirname(__file__))

from ffmpeg_quality_metrics import run_command


def print_stderr(msg):
    print(msg, file=sys.stderr)


def run_calculations(input_file, src_path, output_dir, dry_run=False, verbose=False):
    if not input_file.endswith(".mpd"):
        print_stderr("Need to work with MPD files!")
        sys.exit(1)

    # Root: 1553097052.megalomania9x2.Meridian-2160_crf_28_maxdur_4c0_fix_cbr_3200000.0_job6/crf_28.mpd
    input_dir_basename = os.path.basename(os.path.dirname(input_file))

    try:
        ret = re.match(r'(\d+)\.(\w+)\.(?P<SRC>[a-zA-Z0-9]+)-(\d+)_(.*)', input_dir_basename)
        src = ret.group("SRC")
    except Exception as e:
        print_stderr(f"Could not find SRC in {input_dir_basename}")
        sys.exit(1)

    # SRC: /media/share3/varible-segdurs-srcs/Meridian-2160.avi
    src_file = os.path.join(src_path, src + "-2160.avi")

    if verbose:
        print_stderr(f"Looking for SRC at {src_file}")

    cmd = [
        "python3",
        "ffmpeg_quality_metrics.py",
        input_file,
        src_file,
        "-of", "csv"
    ]

    stdout, stderr = run_command(cmd, dry_run, verbose)

    print(stdout)

    return


def main():
    version = "0.1"
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="scenecut_extractor v" + version,
    )

    parser.add_argument("input", help="input file, distorted")

    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="Do not run command, just show what would be done"
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show verbose output"
    )

    parser.add_argument(
        "-s",
        "--src-path",
        type=str,
        default="/media/share3/varible-segdurs-srcs/"
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default="quality-metrics-results"
    )

    cli_args = parser.parse_args()

    run_calculations(cli_args.input, cli_args.src_path, cli_args.output_dir, cli_args.dry_run, cli_args.verbose)


if __name__ == "__main__":
    main()
