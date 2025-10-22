#!/usr/bin/env python3
#
# ffmpeg-quality-metrics GUI standalone viewer
# Author: Werner Robitza
# License: MIT

import argparse
import logging
import sys

from .__init__ import __version__ as version
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
        description=f"ffmpeg-quality-metrics GUI v{version} - Visualize quality metrics from existing files",
        prog="ffmpeg-quality-metrics-gui",
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        help="Input file(s) (JSON or CSV) containing quality metrics. Multiple files can be provided for comparison.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind the dashboard to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port to bind the dashboard to",
    )
    parser.add_argument(
        "--framerate",
        type=float,
        default=None,
        help="Frame rate for time axis calculation (if not available in the data)",
    )

    cli_args = parser.parse_args()

    setup_logger(logging.DEBUG if cli_args.verbose else logging.INFO)

    try:
        # Import GUI module (may fail if dependencies not installed)
        from .gui import load_multiple_metrics_files, run_dashboard

        # Load the metrics files
        if len(cli_args.input_files) == 1:
            logger.info(f"Loading metrics from {cli_args.input_files[0]}")
        else:
            logger.info(
                f"Loading metrics from {len(cli_args.input_files)} files for comparison"
            )
        data = load_multiple_metrics_files(
            cli_args.input_files, framerate=cli_args.framerate
        )

        # Run the dashboard
        run_dashboard(
            data,
            host=cli_args.host,
            port=cli_args.port,
            debug=cli_args.verbose,
        )

    except ImportError as e:
        logger.error(
            f"GUI dependencies not installed: {e}\n"
            "Please install with: pip install 'ffmpeg-quality-metrics[gui]'"
        )
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if cli_args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
