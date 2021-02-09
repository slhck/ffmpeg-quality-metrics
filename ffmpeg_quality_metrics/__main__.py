#!/usr/bin/env python3
#
# Calculate SSIM/PSNR from video
#
# See also: https://github.com/stoyanovgeorge/ffmpeg/wiki/How-to-Compare-Video
#
# Author: Werner Robitza
# License: MIT

from functools import reduce
import argparse
import subprocess
import os
import json
import sys
import tempfile
import pandas as pd
import numpy as np
from platform import system as _current_os
from shutil import which
import re

from .__init__ import __version__ as version

ALLOWED_SCALERS = [
    "fast_bilinear",
    "bilinear",
    "bicubic",
    "experimental",
    "neighbor",
    "area",
    "bicublin",
    "gauss",
    "sinc",
    "lanczos",
    "spline",
]
CUR_OS = _current_os()
IS_WIN = CUR_OS in ["Windows", "cli"]
IS_NIX = (not IS_WIN) and any(
    CUR_OS.startswith(i)
    for i in ["CYGWIN", "MSYS", "Linux", "Darwin", "SunOS", "FreeBSD", "NetBSD"]
)
NUL = "NUL" if IS_WIN else "/dev/null"


def win_path_check(path):
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


def get_brewed_model_path():
    """
    Hack to get path for VMAF model from Linuxbrew
    """
    stdout, _ = run_command(["brew", "--prefix", "libvmaf"])
    cellar_path = stdout.strip()

    model_path = os.path.join(cellar_path, "share", "model")

    return model_path


def print_error(msg):
    print("ERROR: %s" % msg, file=sys.stderr)


def print_warning(msg):
    print("WARNING: %s" % msg, file=sys.stderr)


def print_info(msg):
    print("INFO: %s" % msg, file=sys.stderr)


def run_command(cmd, dry_run=False, verbose=False, allow_error=False):
    """
    Run a command directly
    """
    if dry_run or verbose:
        print_info("[cmd] " + " ".join(cmd))
        if dry_run:
            return

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if allow_error or process.returncode == 0:
        return stdout.decode("utf-8"), stderr.decode("utf-8")
    else:
        print_error("error running command: {}".format(" ".join(cmd)))
        print_error(stderr.decode("utf-8"))
        sys.exit(1)


def get_framerate(input_file):
    cmd = ["ffmpeg", "-nostdin", "-y", "-i", input_file]

    output = run_command(cmd, allow_error=True)
    pattern = re.compile(r"(\d+(\.\d+)?) fps")
    try:
        match = pattern.search(str(output)).groups()[0]
        return float(match)
    except Exception as e:
        print_error(f"could not parse FPS from file {input_file}!")
        sys.exit(1)


def get_framerates(ref, dist):
    ref_framerate = get_framerate(ref)
    dist_framerate = get_framerate(dist)

    if ref_framerate != dist_framerate:
        print_warning(
            f"ref, dist framerates differ: {ref_framerate}, {dist_framerate}. "
            "This may result in inaccurate quality metrics. Force an input framerate via the -r option."
        )

    return ref_framerate, dist_framerate


def calc_vmaf(
    ref,
    dist,
    model_path,
    scaling_algorithm="bicubic",
    phone_model=False,
    framerate=None,
    dry_run=False,
    verbose=False,
    threads=0,
    n_threads=os.cpu_count()
):
    vmaf_data = []

    if scaling_algorithm not in ALLOWED_SCALERS:
        print_error(f"Allowed scaling algorithms: {ALLOWED_SCALERS}")
        sys.exit(1)

    try:
        temp_dir = tempfile.gettempdir()

        temp_file_name_vmaf = os.path.join(
            temp_dir, next(tempfile._get_candidate_names()) + "-vmaf.txt"
        )

        if verbose:
            print_info(
                f"Writing temporary VMAF information to: {temp_file_name_vmaf}"
            )

        vmaf_opts = {
            "model_path": win_path_check(model_path),
            "phone_model": "1" if phone_model else "0",
            "log_path": win_path_check(temp_file_name_vmaf),
            "log_fmt": "json",
            "psnr": "1",
            "ssim": "1",
            "ms_ssim": "1",
            "n_threads": str(n_threads)
        }

        vmaf_opts_string = ":".join(f"{k}={v}" for k, v in vmaf_opts.items())

        filter_chains = [
            f"[1][0]scale2ref=flags={scaling_algorithm}[dist][ref]",
            "[dist]setpts=PTS-STARTPTS[dist1]",
            "[ref]setpts=PTS-STARTPTS[ref1]",
            f"[dist1][ref1]libvmaf='{vmaf_opts_string}'",
        ]

        cmd = get_ffmpeg_command(ref, dist, filter_chains, framerate, threads)

        run_command(cmd, dry_run, verbose)

        if not dry_run:
            with open(temp_file_name_vmaf, "r") as in_vmaf:
                vmaf_log = json.load(in_vmaf)
                for frame_data in vmaf_log["frames"]:
                    # append frame number, increase +1
                    frame_data["metrics"]["n"] = int(frame_data["frameNum"]) + 1
                    vmaf_data.append(frame_data["metrics"])

    except Exception as e:
        raise e
    finally:
        if os.path.isfile(temp_file_name_vmaf):
            os.remove(temp_file_name_vmaf)

    return vmaf_data


def get_ffmpeg_command(ref, dist, filter_chains=[], framerate=None, threads=0):
    if not framerate:
        ref_framerate, dist_framerate = get_framerates(ref, dist)
    else:
        ref_framerate = framerate
        dist_framerate = framerate

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-threads",
        str(threads),
        "-r",
        str(ref_framerate),
        "-i",
        ref,
        "-r",
        str(dist_framerate),
        "-i",
        dist,
        "-filter_complex",
        ";".join(filter_chains),
        "-an",
        "-f",
        "null",
        NUL,
    ]

    return cmd


def calc_ssim_psnr(
    ref, dist, scaling_algorithm="bicubic", framerate=None, dry_run=False, verbose=False, threads=0
):
    psnr_data = []
    ssim_data = []

    if scaling_algorithm not in ALLOWED_SCALERS:
        print_error(f"Allowed scaling algorithms: {ALLOWED_SCALERS}")
        sys.exit(1)

    try:
        temp_dir = tempfile.gettempdir()

        temp_file_name_ssim = os.path.join(
            temp_dir, next(tempfile._get_candidate_names()) + "-ssim.txt"
        )
        temp_file_name_psnr = os.path.join(
            temp_dir, next(tempfile._get_candidate_names()) + "-psnr.txt"
        )

        if verbose:
            print_info(
                f"Writing temporary SSIM information to: {temp_file_name_ssim}"
            )
            print_info(
                f"Writing temporary PSNR information to: {temp_file_name_psnr}"
            )

        filter_chains = [
            f"[1][0]scale2ref=flags={scaling_algorithm}[dist][ref]",
            "[dist]setpts=PTS-STARTPTS[distpts]",
            "[ref]setpts=PTS-STARTPTS[refpts]",
            "[distpts]split[dist1][dist2]",
            "[refpts]split[ref1][ref2]",
            f"[dist1][ref1]psnr='{win_path_check(temp_file_name_psnr)}'",
            f"[dist2][ref2]ssim='{win_path_check(temp_file_name_ssim)}'",
        ]

        cmd = get_ffmpeg_command(ref, dist, filter_chains, framerate, threads)

        run_command(cmd, dry_run, verbose)

        if not dry_run:
            with open(temp_file_name_psnr, "r") as in_psnr:
                # n:1 mse_avg:529.52 mse_y:887.00 mse_u:233.33 mse_v:468.25 psnr_avg:20.89 psnr_y:18.65 psnr_u:24.45 psnr_v:21.43
                lines = in_psnr.readlines()
                for line in lines:
                    line = line.strip()
                    fields = line.split(" ")
                    frame_data = {}
                    for field in fields:
                        k, v = field.split(":")
                        frame_data[k] = round(float(v), 3) if k != "n" else int(v)
                    psnr_data.append(frame_data)

            with open(temp_file_name_ssim, "r") as in_ssim:
                # n:1 Y:0.937213 U:0.961733 V:0.945788 All:0.948245 (12.860441)\n
                lines = in_ssim.readlines()
                for line in lines:
                    line = line.strip().split(" (")[0]  # remove excess
                    fields = line.split(" ")
                    frame_data = {}
                    for field in fields:
                        k, v = field.split(":")
                        if k != "n":
                            # make psnr and ssim keys the same
                            k = "ssim_" + k.lower()
                            k = k.replace("all", "avg")
                        frame_data[k] = round(float(v), 3) if k != "n" else int(v)
                    ssim_data.append(frame_data)

    except Exception as e:
        raise e
    finally:
        if os.path.isfile(temp_file_name_psnr):
            os.remove(temp_file_name_psnr)
        if os.path.isfile(temp_file_name_ssim):
            os.remove(temp_file_name_ssim)

    return {"ssim": ssim_data, "psnr": psnr_data}


def calculate_global_stats(ret):
    global_stats = {}
    for key in ["ssim", "psnr", "vmaf"]:
        if key not in ret:
            continue

        value_key = key if key == "vmaf" else key + "_avg"
        values = [float(entry[value_key]) for entry in ret[key]]
        global_stats[key] = {
            "average": np.average(values),
            "stdev": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
        }

    return global_stats


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="ffmpeg_quality_metrics v" + version,
    )
    parser.add_argument("dist", help="input file, distorted")
    parser.add_argument("ref", help="input file, reference")

    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Do not run command, just show what would be done",
    )

    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Show verbose output"
    )

    parser.add_argument(
        "-ev",
        "--enable-vmaf",
        action="store_true",
        help="Enable VMAF computation; calculates VMAF as well as SSIM and PSNR",
    )

    parser.add_argument(
        "-m", "--model-path",
        type=str,
        default='vmaf_models/vmaf_v0.6.1.json',
        help="Use a specific model file. You must specify the path"
    )

    parser.add_argument(
        "-p", "--phone-model", 
        action="store_true", 
        help="Enable VMAF phone model"
    )

    parser.add_argument(
        "-dp",
        "--disable-psnr-ssim",
        action="store_true",
        help="Disable PSNR/SSIM computation. Use VMAF to get YUV estimate.",
    )

    parser.add_argument(
        "-s",
        "--scaling-algorithm",
        default="bicubic",
        choices=ALLOWED_SCALERS,
        help="Scaling algorithm for ffmpeg",
    )
    parser.add_argument(
        "-of",
        "--output-format",
        type=str,
        default="json",
        choices=["json", "csv"],
        help="Output format for the metrics",
    )
    parser.add_argument(
        "-r", "--framerate", 
        type=float, 
        help="Force an input framerate",
    )

    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=0,
        help="Number of threads to do the calculations",
    )

    parser.add_argument(
        "-nt",
        "--n-threads",
        type=int,
        default=os.cpu_count(),
        help="Set the value of libvmaf\'s n_threads option. "
             "This determines the number of threads that are used for VMAF calculation"
    )

    cli_args = parser.parse_args()

    ret = {}

    if cli_args.enable_vmaf:
        if not cli_args.model_path:
            model_path = 'vmaf_models/vmaf_v0.6.1.json'
            # If the user installed ffmpeg using homebrew 
            if has_brew() and ffmpeg_is_from_brew():
                model_path = os.path.join(
                    # FIXME: change this once VMAF 2.0 is bundled with homebrew!
                    get_brewed_model_path(), "vmaf_v0.6.1.pkl"
                )   
        else:  # The model path was specified manually.
            model_path = cli_args.model_path
            if model_path != 'vmaf_models/vmaf_v0.6.1.json' and not os.path.isfile(model_path):
                # Without model_path != 'vmaf_models/vmaf_v0.6.1.json', for some reason there is the following error:
                # "Could not find model at vmaf_models/vmaf_v0.6.1.json"
                print_error(
                    f"Could not find model at {model_path}. Please set --model-path to a valid VMAF .pkl or .json model file."
                )
                sys.exit(1)

        ret["vmaf"] = calc_vmaf(
            cli_args.ref,
            cli_args.dist,
            model_path,
            cli_args.scaling_algorithm,
            cli_args.phone_model,
            cli_args.framerate,
            cli_args.dry_run,
            cli_args.verbose,
            cli_args.threads,
            cli_args.n_threads
        )

    if not cli_args.disable_psnr_ssim:
        ret_tmp = calc_ssim_psnr(
            cli_args.ref,
            cli_args.dist,
            cli_args.scaling_algorithm,
            cli_args.framerate,
            cli_args.dry_run,
            cli_args.verbose,
            cli_args.threads,

        )
        ret["psnr"] = ret_tmp["psnr"]
        ret["ssim"] = ret_tmp["ssim"]

    if cli_args.dry_run:
        print_warning("Dry run specified, exiting without computing stats")
        return

    if cli_args.output_format == "json":
        ret["global"] = calculate_global_stats(ret)
        ret["input_file_dist"] = cli_args.dist
        ret["input_file_ref"] = cli_args.ref
        print(json.dumps(ret, indent=4))

    elif cli_args.output_format == "csv":
        all_dfs = []

        if "vmaf" in ret:
            all_dfs.append(pd.DataFrame(ret["vmaf"]))

        if "psnr" in ret and "ssim" in ret:
            all_dfs.append(pd.DataFrame(ret["psnr"]))
            all_dfs.append(pd.DataFrame(ret["ssim"]))

        if not all_dfs:
            print_error("No data calculated!")
            sys.exit(1)

        try:
            df = reduce(lambda x, y: pd.merge(x, y, on="n"), all_dfs)

            df["input_file_dist"] = cli_args.dist
            df["input_file_ref"] = cli_args.ref

            cols = df.columns.tolist()
            cols.insert(0, cols.pop(cols.index("n")))
            df = df.reindex(columns=cols)
            print(df.to_csv(index=False))
        except Exception as e:
            print_error(f"Error merging data to CSV: {e}")
            sys.exit(1)
    else:
        print_error("Wrong output format chosen, use 'json' or 'csv'")
        sys.exit(1)


if __name__ == "__main__":
    main()
