#!/usr/bin/env python3
#
# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

import argparse
import sys

from .ffmpeg_quality_metrics import FfmpegQualityMetrics
from .utils import print_error, print_warning

from .__init__ import __version__ as version


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="ffmpeg_quality_metrics v" + version,
    )
    parser.add_argument("dist", help="input file, distorted")
    parser.add_argument("ref", help="input file, reference")

    general_opts = parser.add_argument_group("General options")

    general_opts.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Do not run commands, just show what would be done",
    )
    general_opts.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    general_opts.add_argument(
        "-p", "--progress", action="store_true", help="Show a progress bar"
    )
    general_opts.add_argument(
        "-k", "--keep-tmp", action="store_true", help="Keep temporary files for debugging purposes"
    )

    metric_options = parser.add_argument_group("Metric options")

    metric_options.add_argument(
        "-m",
        "--metrics",
        default=["psnr", "ssim"],
        help="Metrics to calculate. Specify multiple metrics like '--metrics ssim vmaf'",
        nargs="+",
        choices=FfmpegQualityMetrics.METRIC_TO_FILTER_MAP.keys(),
    )

    ffmpeg_opts = parser.add_argument_group("FFmpeg options")

    ffmpeg_opts.add_argument(
        "-s",
        "--scaling-algorithm",
        default="bicubic",
        choices=FfmpegQualityMetrics.ALLOWED_SCALERS,
        help="Scaling algorithm for ffmpeg",
    )

    ffmpeg_opts.add_argument(
        "-r", "--framerate", type=float, help="Force an input framerate",
    )

    ffmpeg_opts.add_argument(
        "-t",
        "--threads",
        type=int,
        default=FfmpegQualityMetrics.DEFAULT_THREADS,
        help="Number of threads to do the calculations",
    )

    output_opts = parser.add_argument_group("Output options")

    output_opts.add_argument(
        "-of",
        "--output-format",
        type=str,
        default="json",
        choices=["json", "csv"],
        help="Output format for the metrics",
    )

    vmaf_opts = parser.add_argument_group("VMAF options")

    vmaf_opts.add_argument(
        "--model-path",
        type=str,
        default=FfmpegQualityMetrics.get_default_vmaf_model_path(),
        help="Use a specific VMAF model file. If none is chosen, picks a default model. "
        f"You can also specify one of the following built-in models: {FfmpegQualityMetrics.get_supplied_vmaf_models()}",
    )

    vmaf_opts.add_argument(
        "--phone-model", action="store_true", help="Enable VMAF phone model"
    )

    vmaf_opts.add_argument(
        "--n-threads",
        type=int,
        default=FfmpegQualityMetrics.DEFAULT_VMAF_THREADS,
        help="Set the value of libvmaf's n_threads option. "
        "This determines the number of threads that are used for VMAF calculation",
    )

    cli_args = parser.parse_args()

    ffqm = FfmpegQualityMetrics(
        ref=cli_args.ref,
        dist=cli_args.dist,
        scaling_algorithm=cli_args.scaling_algorithm,
        framerate=cli_args.framerate,
        dry_run=cli_args.dry_run,
        verbose=cli_args.verbose,
        threads=cli_args.threads,
        progress=cli_args.progress,
    )

    metrics = cli_args.metrics

    vmaf_options = {}
    if "vmaf" in metrics:
        vmaf_options = {
            "model_path": cli_args.model_path,
            "phone_model": cli_args.phone_model,
            "n_threads": cli_args.n_threads,
        }

    ffqm.calc(metrics, vmaf_options=vmaf_options)

    if cli_args.dry_run:
        print_warning("Dry run specified, exiting without computing stats")
        return

    if cli_args.output_format == "json":
        print(ffqm.get_results_json())
    elif cli_args.output_format == "csv":
        print(ffqm.get_results_csv())
    else:
        print_error("Wrong output format chosen, use 'json' or 'csv'")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"General exception: {e}")
        print(sys.exc_info())
        sys.exit(1)
