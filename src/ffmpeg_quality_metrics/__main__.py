#!/usr/bin/env python3
#
# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

import argparse
import logging
import sys
import traceback

from .__init__ import __version__ as version
from .ffmpeg_quality_metrics import FfmpegQualityMetrics, VmafOptions
from .log import CustomLogFormatter

logger = logging.getLogger("ffmpeg-quality-metrics")


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("ffmpeg-quality-metrics")
    logger.setLevel(level)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)

    ch.setFormatter(CustomLogFormatter())

    logger.addHandler(ch)

    return logger


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog: argparse.ArgumentDefaultsHelpFormatter(
            prog, max_help_position=40, width=100
        ),
        description="ffmpeg-quality-metrics v" + version,
        prog="ffmpeg-quality-metrics",
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
    general_opts.add_argument(
        "--tmp-dir",
        type=str,
        default=None,
        help="Directory to store temporary files in (will use system default if not specified)",
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
        "--dist-delay",
        type=float,
        default=0.0,
        help="Delay the distorted video against the reference by this many seconds",
    )

    ffmpeg_opts.add_argument(
        "-t",
        "--threads",
        type=int,
        default=FfmpegQualityMetrics.DEFAULT_THREADS,
        help="Number of threads to do the calculations",
    )

    ffmpeg_opts.add_argument(
        "--num-frames",
        type=int,
        default=None,
        help="Number of frames to analyze from the input files (default: all frames)",
    )

    ffmpeg_opts.add_argument(
        "--start-offset",
        type=str,
        default=None,
        help="Seek to this position before analyzing. Accepts timestamp (e.g., '00:00:10' or '10.5') or frame number with 'f:' prefix (e.g., 'f:100'). Note: seeking may not be frame-accurate due to keyframe constraints.",
    )

    ffmpeg_opts.add_argument(
        "--ffmpeg-path",
        type=str,
        default="ffmpeg",
        help="Path to ffmpeg executable",
    )

    output_opts = parser.add_argument_group("Output options")

    output_opts.add_argument(
        "-o",
        "--output-file",
        type=str,
        default=None,
        help="Output file for the metrics. If not specified, stdout will be used.",
    )

    output_opts.add_argument(
        "-of",
        "--output-format",
        type=str,
        default="json",
        choices=["json", "csv"],
        help="Output format for the metrics",
    )

    output_opts.add_argument(
        "--gui",
        action="store_true",
        help="Open interactive GUI dashboard after computing metrics (requires 'gui' extra: pip install 'ffmpeg-quality-metrics[gui]')",
    )

    output_opts.add_argument(
        "--gui-host",
        type=str,
        default="127.0.0.1",
        help="Host address for the GUI dashboard",
    )

    output_opts.add_argument(
        "--gui-port",
        type=int,
        default=8050,
        help="Port for the GUI dashboard",
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
        help="Set the value of libvmaf's n_threads option. This determines the number of threads that are used for VMAF calculation. Set to 0 for auto.",
    )

    vmaf_opts.add_argument(
        "--vmaf-subsample",
        type=int,
        default=FfmpegQualityMetrics.DEFAULT_VMAF_SUBSAMPLE,
        help="Set the value of libvmaf's n_subsample option. This is the subsampling interval, so set to 1 for default behavior.",
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
        dist_delay=cli_args.dist_delay,
        dry_run=cli_args.dry_run,
        verbose=cli_args.verbose,
        threads=cli_args.threads,
        progress=cli_args.progress,
        keep_tmp_files=cli_args.keep_tmp,
        tmp_dir=cli_args.tmp_dir,
        num_frames=cli_args.num_frames,
        start_offset=cli_args.start_offset,
        ffmpeg_path=cli_args.ffmpeg_path,
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
        output_data = ffqm.get_results_json()
    elif cli_args.output_format == "csv":
        output_data = ffqm.get_results_csv()
    else:
        logger.error("Wrong output format chosen, use 'json' or 'csv'")
        sys.exit(1)

    if cli_args.output_file:
        try:
            with open(cli_args.output_file, "w") as f:
                f.write(output_data)
            logger.info(f"Output written to {cli_args.output_file}")
        except Exception as e:
            logger.error(f"Could not write to output file: {e}")
            sys.exit(1)
    else:
        print(output_data)

    # Launch GUI if requested
    if cli_args.gui:
        try:
            from .gui import MetricsData, MultiClipData, run_dashboard

            logger.info("Launching interactive dashboard...")

            # Get framerate for time axis
            ref_framerate, _ = ffqm._get_framerates()

            # Create MetricsData object from results
            gui_data = MetricsData(
                metrics=ffqm.data,  # type: ignore
                global_stats=ffqm.get_global_stats(),  # type: ignore
                input_file_dist=cli_args.dist,
                input_file_ref=cli_args.ref,
                framerate=ref_framerate,
            )

            # Wrap in MultiClipData for dashboard
            multi_clip_data = MultiClipData(clips=[gui_data])

            run_dashboard(
                multi_clip_data,
                host=cli_args.gui_host,
                port=cli_args.gui_port,
                debug=cli_args.verbose,
            )
        except ImportError:
            logger.error(
                "GUI dependencies not installed. Install with: pip install 'ffmpeg-quality-metrics[gui]'"
            )
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error launching GUI: {e}")
            if cli_args.verbose:
                traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"General exception: {e}")
        # print a stacktrace
        traceback.print_exc()
        sys.exit(1)
