#!/usr/bin/env python3
#
# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

import argparse
import sys
import logging
import traceback

from .log import CustomLogFormatter
from .ffmpeg_quality_metrics import FfmpegQualityMetrics, VmafOptions

from .__init__ import __version__ as version

logger = logging.getLogger("ffmpeg-quality-metrics")


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("ffmpeg-quality-metrics")
    logger.setLevel(level)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)

    ch.setFormatter(CustomLogFormatter())

    logger.addHandler(ch)

    return logger


def main():
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog: argparse.ArgumentDefaultsHelpFormatter(
            prog, max_help_position=40, width=100
        ),
        description="ffmpeg_quality_metrics v" + version,
        prog="ffmpeg_quality_metrics",
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
        "-k",
        "--keep-tmp",
        action="store_true",
        help="Keep temporary files for debugging purposes",
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
        "-r",
        "--framerate",
        type=float,
        help="Force an input framerate",
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
        "--vmaf-model-path",
        type=str,
        default=FfmpegQualityMetrics.get_default_vmaf_model_path(),
        help="Use a specific VMAF model file. If none is chosen, picks a default model. "
        f"You can also specify one of the following built-in models: {FfmpegQualityMetrics.get_supplied_vmaf_models()}",
    )

    vmaf_opts.add_argument(
        "--vmaf-model-params",
        type=str,
        nargs="+",
        help="A list of params to pass to the VMAF model, specified as key=value. "
        "Specify multiple params like '--vmaf-model-params enable_transform=true enable_conf_interval=true'",
    )

    vmaf_opts.add_argument(
        "--vmaf-threads",
        type=int,
        default=FfmpegQualityMetrics.DEFAULT_VMAF_THREADS,
        help="Set the value of libvmaf's n_threads option. "
        "This determines the number of threads that are used for VMAF calculation. "
        "Set to 0 for auto.",
    )

    vmaf_opts.add_argument(
        "--vmaf-subsample",
        type=int,
        default=FfmpegQualityMetrics.DEFAULT_VMAF_SUBSAMPLE,
        help="Set the value of libvmaf's n_subsample option. "
        "This is the subsampling interval, so set to 1 for default behavior.",
    )

    vmaf_opts.add_argument(
        "--vmaf-features",
        type=str,
        nargs="+",
        help="A list of feature to enable. Pass the names of the features and any optional params. "
        "See https://github.com/Netflix/vmaf/blob/master/resource/doc/features.md for a list of available features. "
        "Params must be specified as 'key=value'. "
        "Multiple params must be separated by ':'. "
        "Specify multiple features like '--vmaf-features cambi:full_ref=true ciede'",
    )

    cli_args = parser.parse_args()

    setup_logger(logging.DEBUG if cli_args.verbose else logging.INFO)

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

    if "vmaf" in metrics:
        vmaf_options: VmafOptions = {
            "model_path": cli_args.vmaf_model_path,
            "model_params": cli_args.vmaf_model_params,
            "n_threads": cli_args.vmaf_threads,
            "n_subsample": cli_args.vmaf_subsample,
            "features": cli_args.vmaf_features,
        }
        ffqm.calculate(metrics, vmaf_options=vmaf_options)
    else:
        ffqm.calculate(metrics)

    if cli_args.dry_run:
        logger.warning("Dry run specified, exiting without computing stats")
        return

    if cli_args.output_format == "json":
        print(ffqm.get_results_json())
    elif cli_args.output_format == "csv":
        print(ffqm.get_results_csv())
    else:
        logger.error("Wrong output format chosen, use 'json' or 'csv'")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"General exception: {e}")
        # print a stacktrace
        traceback.print_exc()
        sys.exit(1)
