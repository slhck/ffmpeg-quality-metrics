# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

import json
import logging
import os
import re
import tempfile
from functools import reduce
from typing import Dict, List, Literal, Tuple, TypedDict, Union, cast

import numpy as np
import pandas as pd
from ffmpeg_progress_yield import FfmpegProgress
from packaging.version import Version
from packaging.version import parse as parse_version
from tqdm import tqdm

from .utils import (
    NUL,
    ffmpeg_is_from_brew,
    has_brew,
    quoted_cmd,
    run_command,
    win_path_check,
    win_vmaf_model_path_check,
)

logger = logging.getLogger("ffmpeg-quality-metrics")

# =====================================================================================================================
# TYPE DEFINITIONS


class VmafOptions(TypedDict):
    """
    VMAF-specific options.
    """

    model_path: Union[str, None]
    """Use a specific VMAF model file. If none is chosen, picks a default model."""
    model_params: List[str]
    """A list of params to pass to the VMAF model, specified as key=value."""
    n_threads: Union[int, None]
    """Number of threads to use. Defaults to 0 (auto)."""
    n_subsample: Union[int, None]
    """Subsampling interval. Defaults to 1."""
    features: List[str]
    """
    List of features to enable in addition to the default features.
    Each entry must be a string beginning with name=feature_name, and additional parameters can be specified as
    key=value, separated by colons.
    """


MetricName = Literal["psnr", "ssim", "vmaf", "vif"]
"""The name of a metric."""

FilterName = Literal["psnr", "ssim", "libvmaf", "vif"]
"""The name of an ffmpeg filter used for that metric."""

SingleMetricData = List[Dict[str, float]]
"""A per-frame list of metric values."""

GlobalStatsData = Dict[str, float]
"""A dict of global stats for a metric."""

GlobalStats = Dict[MetricName, Dict[str, GlobalStatsData]]
"""A dict of global stats for all metrics."""

MetricData = Dict[MetricName, SingleMetricData]
"""A dict of per-frame metric values for all metrics."""


# =====================================================================================================================
# MAIN CLASSES


class FfmpegQualityMetricsError(Exception):
    pass


class FfmpegQualityMetrics:
    """
    A class to calculate quality metrics with FFmpeg
    """

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
    DEFAULT_SCALER = "bicubic"
    DEFAULT_THREADS = 0

    DEFAULT_VMAF_THREADS = 0  # used to be os.cpu_count(), now auto
    DEFAULT_VMAF_SUBSAMPLE = 1  # sample every frame
    DEFAULT_VMAF_MODEL_DIRECTORY = os.path.join(
        os.path.dirname(__file__), "vmaf_models"
    )
    DEFAULT_VMAF_OPTIONS: VmafOptions = {
        "model_path": None,
        "model_params": [],
        "n_threads": DEFAULT_VMAF_THREADS,
        "n_subsample": DEFAULT_VMAF_SUBSAMPLE,
        "features": [],
    }
    POSSIBLE_FILTERS: List[FilterName] = [
        "libvmaf",
        "psnr",
        "ssim",
        "vif",
    ]  # , "identity", "msad"]
    METRIC_TO_FILTER_MAP: Dict[MetricName, FilterName] = {
        "vmaf": "libvmaf",
        "psnr": "psnr",
        "ssim": "ssim",
        "vif": "vif",
        # "identity": "identity",
        # "msad": "msad",
    }

    def __init__(
        self,
        ref: str,
        dist: str,
        scaling_algorithm: str = DEFAULT_SCALER,
        framerate: Union[float, None] = None,
        dist_delay: float = 0,
        dry_run: Union[bool, None] = False,
        verbose: Union[bool, None] = False,
        threads: int = DEFAULT_THREADS,
        progress: Union[bool, None] = False,
        keep_tmp_files: Union[bool, None] = False,
        tmp_dir: Union[str, None] = None,
    ):
        """Instantiate a new FfmpegQualityMetrics

        Args:
            ref (str): reference file
            dist (str): distorted file
            scaling_algorithm (str, optional): A scaling algorithm. Must be one of the following: ["fast_bilinear", "bilinear", "bicubic", "experimental", "neighbor", "area", "bicublin", "gauss", "sinc", "lanczos", "spline"]. Defaults to "bicubic"
            framerate (float, optional): Force a frame rate. Defaults to None.
            dist_delay (float): Delay the distorted file against the reference by this amount of seconds. Defaults to 0.
            dry_run (bool, optional): Don't run anything, just print commands. Defaults to False.
            verbose (bool, optional): Show more output. Defaults to False.
            threads (int, optional): Number of ffmpeg threads. Defaults to 0 (auto).
            progress (bool, optional): Show a progress bar. Defaults to False.
            keep_tmp_files (bool, optional): Keep temporary files for debugging purposes. Defaults to False.
            tmp_dir (str, optional): Directory to store temporary files. Will use system default if not specified. Defaults to None.

        Raises:
            FfmpegQualityMetricsError: A generic error
        """
        self.ref = str(ref)
        self.dist = str(dist)
        self.scaling_algorithm = str(scaling_algorithm)
        self.framerate = float(framerate) if framerate is not None else None
        self.dist_delay = float(dist_delay)
        self.dry_run = bool(dry_run)
        self.verbose = bool(verbose)
        self.threads = int(threads)
        self.progress = bool(progress)
        self.keep_tmp_files = bool(keep_tmp_files)
        self.tmp_dir = str(tmp_dir) if tmp_dir is not None else tempfile.gettempdir()

        if not os.path.isfile(self.ref):
            raise FfmpegQualityMetricsError(f"Reference file not found: {self.ref}")
        if not os.path.isfile(self.dist):
            raise FfmpegQualityMetricsError(f"Distorted file not found: {self.dist}")

        if self.ref == self.dist:
            logger.warning(
                "Reference and distorted files are the same! This may lead to unexpected results or numerical issues."
            )

        if ref.endswith(".yuv") or dist.endswith(".yuv"):
            raise FfmpegQualityMetricsError(
                "YUV files are not supported, please convert to a format that ffmpeg can read natively, such as Y4M or FFV1."
            )

        self.data: MetricData = {
            "vmaf": [],
            "psnr": [],
            "ssim": [],
            "vif": [],
            # "identity": [],
            # "msad": [],
        }

        self.available_filters: List[str] = []

        self.global_stats: GlobalStats = {}

        if not os.path.isdir(self.tmp_dir):
            logger.debug(f"Creating temporary directory: {self.tmp_dir}")
            os.makedirs(self.tmp_dir)
        self.temp_files: Dict[FilterName, str] = {}

        for filter_name in self.POSSIBLE_FILTERS:
            suffix = "txt" if filter_name != "libvmaf" else "json"

            self.temp_files[cast(FilterName, filter_name)] = os.path.join(
                self.tmp_dir,
                f"ffmpeg_quality_metrics_{filter_name}_{os.path.basename(self.ref)}_{os.path.basename(self.dist)}.{suffix}",
            )
            logger.debug(
                f"Writing temporary {filter_name.upper()} information to: {self.temp_files[cast(FilterName, filter_name)]}"
            )

        if scaling_algorithm not in self.ALLOWED_SCALERS:
            raise FfmpegQualityMetricsError(
                f"Allowed scaling algorithms: {self.ALLOWED_SCALERS}"
            )

        self._check_available_filters()

    def _check_available_filters(self):
        """
        Check which filters are available
        """
        cmd = ["ffmpeg", "-filters"]
        stdout, _ = run_command(cmd)
        filter_list = []
        for line in stdout.split("\n"):
            line = line.strip()
            if line == "":
                continue
            cols = line.split(" ")
            if len(cols) > 1:
                filter_name = cols[1]
                filter_list.append(filter_name)

        for key in FfmpegQualityMetrics.POSSIBLE_FILTERS:
            if key in filter_list:
                self.available_filters.append(key)

        logger.debug(f"Available filters: {self.available_filters}")

    @staticmethod
    def get_ffmpeg_version() -> Version:
        """
        Get the version of ffmpeg
        """
        cmd = ["ffmpeg", "-version"]
        stdout, _ = run_command(cmd)
        # $ ffmpeg -version
        # ffmpeg version 7.1.1 Copyright (c) 2000-2025 the FFmpeg developers
        # ...
        version_str = stdout.split("\n")[0].split(" ")[2]
        # Clean the version string by removing the "-static" suffix if it exists
        version_str = version_str.split("-")[0]
        return parse_version(version_str)

    @staticmethod
    def get_framerate(input_file: str) -> float:
        """Parse the FPS from the input file.

        Args:
            input_file (str): Input file path

        Raises:
            FfmpegQualityMetricsError: A generic error

        Returns:
            float: The FPS parsed
        """
        cmd = ["ffmpeg", "-nostdin", "-y", "-i", input_file]

        output = run_command(cmd, allow_error=True)
        pattern = re.compile(r"(\d+(\.\d+)?) fps")
        try:
            if pattern_ret := pattern.search(str(output)):
                match = pattern_ret.groups()[0]
                return float(match)
        except Exception:
            pass

        raise FfmpegQualityMetricsError(f"could not parse FPS from file {input_file}!")

    def _get_framerates(self) -> Tuple[float, float]:
        """
        Get the framerates of the reference and distorted files.

        Returns:
            Tuple[float, float]: The framerates of the reference and distorted files
        """
        ref_framerate = FfmpegQualityMetrics.get_framerate(self.ref)
        dist_framerate = FfmpegQualityMetrics.get_framerate(self.dist)

        if ref_framerate != dist_framerate:
            logger.warning(
                f"ref, dist framerates differ: {ref_framerate}, {dist_framerate}. "
                "This may result in inaccurate quality metrics. Force an input framerate via the -r option."
            )

        return ref_framerate, dist_framerate

    def _get_filter_opts(self, filter_name: FilterName) -> str:
        """
        Returns:
            str: Specific ffmpeg filter options for a chosen metric filter.
        """
        if filter_name in ["ssim", "psnr"]:
            return f"{filter_name}='{win_path_check(self.temp_files[filter_name])}'"
        elif filter_name == "libvmaf":
            return f"libvmaf='{self._get_libvmaf_filter_opts()}'"
        elif filter_name == "vif":
            return "vif,metadata=mode=print"
        else:
            raise FfmpegQualityMetricsError(f"Unknown filter {filter_name}!")

    def calculate(
        self,
        metrics: List[MetricName] = ["ssim", "psnr"],
        vmaf_options: Union[VmafOptions, None] = None,
    ) -> Dict[MetricName, SingleMetricData]:
        """Calculate one or more metrics.

        Args:
            metrics (list, optional): A list of metrics to calculate.
                Possible values are ["ssim", "psnr", "vmaf"].
                Defaults to ["ssim", "psnr"].
            vmaf_options (dict, optional): VMAF-specific options. Uses defaults if not specified.

        Raises:
            FfmpegQualityMetricsError: In case of an error
            e: A generic error

        Returns:
            dict: A dictionary of per-frame info, with the key being the metric name and the value being a dict of frame numbers ('n') and metric values.
        """
        if not metrics:
            raise FfmpegQualityMetricsError("No metrics specified!")

        # check available metrics
        for metric_name in metrics:
            filter_name = self.METRIC_TO_FILTER_MAP.get(metric_name, None)
            if filter_name not in self.POSSIBLE_FILTERS:
                raise FfmpegQualityMetricsError(f"No such metric '{metric_name}'")
            if filter_name not in self.available_filters:
                raise FfmpegQualityMetricsError(
                    f"Your ffmpeg version does not have the filter '{filter_name}'"
                )

        # set VMAF options specifically
        if "vmaf" in metrics:
            self._check_libvmaf_availability()
            self.vmaf_options = self.DEFAULT_VMAF_OPTIONS
            # override with user-supplied options
            if vmaf_options:
                for key, value in vmaf_options.items():
                    if value is not None:
                        self.vmaf_options[key] = value  # type: ignore
            self._set_vmaf_model_path(self.vmaf_options["model_path"])

        ffmpeg_version = FfmpegQualityMetrics.get_ffmpeg_version()
        if ffmpeg_version < parse_version("7.1"):
            logger.warning(
                "FFmpeg version is less than 7.1. Using deprecated scale2ref filter. Please update to 7.1 or higher."
            )
            filter_chains = [
                f"[1][0]scale2ref=flags={self.scaling_algorithm}[dist][ref]",
                "[dist]settb=AVTB,setpts=PTS-STARTPTS[distpts]",
                "[ref]settb=AVTB,setpts=PTS-STARTPTS[refpts]",
            ]
        else:
            # ffmpeg 7.1 or higher: scale2ref filter is deprecated
            # input 0: ref, input 1: dist --> swapped for scale filter
            filter_chains = [
                f"[1][0]scale=rw:rh:flags={self.scaling_algorithm}[dist]",
                "[dist]settb=AVTB,setpts=PTS-STARTPTS[distpts]",
                "[0]settb=AVTB,setpts=PTS-STARTPTS[refpts]",
            ]

        # generate split filters depending on the number of models
        n_splits = len(metrics)
        if n_splits > 1:
            for source in ["dist", "ref"]:
                suffixes = "".join([f"[{source}{n}]" for n in range(1, n_splits + 1)])
                filter_chains.extend(
                    [
                        f"[{source}pts]split={n_splits}{suffixes}",
                    ]
                )

        # special case, only one metric:
        if n_splits == 1:
            metric_name = metrics[0]
            filter_chains.extend(
                [
                    f"[distpts][refpts]{self._get_filter_opts(self.METRIC_TO_FILTER_MAP[metric_name])}"
                ]
            )
        # all other cases:
        else:
            for n, metric_name in zip(range(1, n_splits + 1), metrics):
                filter_chains.extend(
                    [
                        f"[dist{n}][ref{n}]{self._get_filter_opts(self.METRIC_TO_FILTER_MAP[metric_name])}"
                    ]
                )

        try:
            output = self._run_ffmpeg_command(filter_chains, desc=", ".join(metrics))
            self._read_temp_files(metrics)
            if output:
                self._read_ffmpeg_output(output, metrics)
            else:
                raise FfmpegQualityMetricsError("ffmpeg output is empty!")
        except Exception as e:
            raise e
        finally:
            self._cleanup_temp_files()

        # return only those data entries containing values
        return cast(
            Dict[MetricName, SingleMetricData],
            {k: v for k, v in self.data.items() if v},
        )

    def _get_libvmaf_filter_opts(self) -> str:
        """
        Returns:

            str: A string to use for VMAF in ffmpeg filter chain
        """
        # we only have one model, and its path parameter is not optional
        all_model_params: Dict[str, str] = {
            "path": win_vmaf_model_path_check(self.vmaf_model_path)
        }

        # add further model parameters
        for model_param in self.vmaf_options["model_params"]:
            key, value = model_param.split("=")
            all_model_params[key] = value

        all_model_params_str = "\\:".join(
            f"{k}={v}" for k, v in all_model_params.items()
        )

        vmaf_opts: Dict[str, str] = {
            "model": all_model_params_str,
            "log_path": win_path_check(self.temp_files["libvmaf"]),
            "log_fmt": "json",
            "n_threads": str(self.vmaf_options["n_threads"]),
            "n_subsample": str(self.vmaf_options["n_subsample"]),
        }

        if self.vmaf_options["features"]:
            features = []
            for feature in self.vmaf_options["features"]:
                if not feature.startswith("name"):
                    feature = f"name={feature}"
                features.append(feature.replace(":", "\\:"))
            vmaf_opts["feature"] = "|".join(features)

        vmaf_opts_string = ":".join(
            f"{k}={v}" for k, v in vmaf_opts.items() if v is not None
        )

        return vmaf_opts_string

    def _check_libvmaf_availability(self) -> None:
        if "libvmaf" not in self.available_filters:
            raise FfmpegQualityMetricsError(
                "Your ffmpeg build does not have support for VMAF. "
                "Make sure you download or build a version compiled with --enable-libvmaf!"
            )

    def _set_vmaf_model_path(self, model_path: Union[str, None] = None) -> None:
        """
        Logic to set the model path depending on the default or the user-supplied string
        """
        if model_path is None:
            self.vmaf_model_path = FfmpegQualityMetrics.get_default_vmaf_model_path()
        else:
            self.vmaf_model_path = str(model_path)

        supplied_models = FfmpegQualityMetrics.get_supplied_vmaf_models()

        if not os.path.isfile(self.vmaf_model_path):
            # check if this is one of the supplied ones? e.g. user passed only a filename
            if self.vmaf_model_path in supplied_models:
                self.vmaf_model_path = os.path.join(
                    FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY,
                    self.vmaf_model_path,
                )
            else:
                raise FfmpegQualityMetricsError(
                    f"Could not find model at {self.vmaf_model_path}. "
                    "Please set --model-path to a valid VMAF .json model file."
                )

    def _read_vmaf_temp_file(self) -> None:
        """
        Read the VMAF temp file and append the data to the data dict.
        """
        with open(self.temp_files["libvmaf"], "r") as in_vmaf:
            vmaf_log = json.load(in_vmaf)
            logger.debug(f"VMAF log: {json.dumps(vmaf_log, indent=4)}")
            for frame_data in vmaf_log["frames"]:
                # append frame number, increase +1
                frame_data["metrics"]["n"] = int(frame_data["frameNum"]) + 1
                self.data["vmaf"].append(frame_data["metrics"])

    def _read_ffmpeg_output(self, ffmpeg_output: str, metrics=[]) -> None:
        """
        Read the metric values from ffmpeg's stderr, for those that don't output
        to a file.
        """
        if self.dry_run:
            return
        if "vif" in metrics:
            self._read_vif_output(ffmpeg_output)

    def _read_vif_output(self, ffmpeg_output: str) -> None:
        """
        Parse the VIF filter output
        """
        # [Parsed_metadata_4 @ 0x7f995cd08640] frame:1    pts:1       pts_time:0.0401x
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.0=0.263582
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.1=0.560129
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.2=0.626596
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.3=0.682183

        lines = [line.strip() for line in ffmpeg_output.split("\n")]
        current_frame = None
        frame_data: Dict[str, float] = {}

        for line in lines:
            if not line.startswith("[Parsed_metadata"):
                continue

            fields = line.split(" ")

            # a new frame appears
            if fields[3].startswith("frame"):
                # if we have data already
                if frame_data:
                    self.data["vif"].append(frame_data)

                # get the frame number and reset the frame data
                current_frame = int(fields[3].split(":")[1])
                frame_data = {"n": current_frame}
                continue

            # no frame was set, or no VIF info present
            if current_frame is None or not fields[3].startswith("lavfi.vif"):
                continue

            # we have a frame
            key, value = fields[3].split("=")
            key = key.replace("lavfi.vif.", "").replace(".", "_")
            frame_data[key] = round(float(value), 3)

        # append final frame data
        if frame_data:
            self.data["vif"].append(frame_data)

    def _read_temp_files(self, metrics=[]):
        """
        Read the data from multiple temp files
        """
        if self.dry_run:
            return
        if "vmaf" in metrics:
            self._read_vmaf_temp_file()
        if "ssim" in metrics:
            self._read_ssim_temp_file()
        if "psnr" in metrics:
            self._read_psnr_temp_file()

    def _run_ffmpeg_command(
        self, filter_chains: List[str] = [], desc: str = ""
    ) -> Union[str, None]:
        """
        Run the ffmpeg command to get the quality metrics.
        The filter chains must be specified manually.
        'desc' can be a human readable description for the progress bar.

        Returns:
            Union[str, None]: The output of ffmpeg's stderr
        """
        if not self.framerate:
            ref_framerate, dist_framerate = self._get_framerates()
        else:
            ref_framerate = self.framerate
            dist_framerate = self.framerate

        cmd = [
            "ffmpeg",
            "-nostdin",
            "-nostats",
            "-y",
            "-threads",
            str(self.threads),
            "-r",
            str(ref_framerate),
            "-i",
            self.ref,
            "-itsoffset",
            str(self.dist_delay),
            "-r",
            str(dist_framerate),
            "-i",
            self.dist,
            "-filter_complex",
            ";".join(filter_chains),
            "-an",
            "-f",
            "null",
            NUL,
        ]

        if self.progress:
            logger.debug(quoted_cmd(cmd))
            ff = FfmpegProgress(cmd, self.dry_run)
            with tqdm(total=100, position=1, desc=desc) as pbar:
                for progress in ff.run_command_with_progress():
                    pbar.update(progress - pbar.n)
            return ff.stderr
        else:
            _, stderr = run_command(cmd, dry_run=self.dry_run)
            return stderr

    def _cleanup_temp_files(self) -> None:
        """
        Remove the temporary files
        """
        for temp_file in self.temp_files.values():
            if os.path.isfile(temp_file):
                if self.keep_tmp_files:
                    logger.debug(f"Keeping temp file {temp_file}")
                else:
                    os.remove(temp_file)

    def _read_psnr_temp_file(self) -> None:
        """
        Parse the PSNR generated logfile
        """
        with open(self.temp_files["psnr"], "r") as in_psnr:
            # n:1 mse_avg:529.52 mse_y:887.00 mse_u:233.33 mse_v:468.25 psnr_avg:20.89 psnr_y:18.65 psnr_u:24.45 psnr_v:21.43
            lines = in_psnr.readlines()
            for line in lines:
                line = line.strip()
                fields = line.split(" ")
                frame_data = {}
                for field in fields:
                    k, v = field.split(":")
                    frame_data[k] = round(float(v), 3) if k != "n" else int(v)
                self.data["psnr"].append(frame_data)

    def _read_ssim_temp_file(self) -> None:
        """
        Parse the SSIM generated logfile
        """
        with open(self.temp_files["ssim"], "r") as in_ssim:
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
                self.data["ssim"].append(frame_data)

    @staticmethod
    def get_brewed_vmaf_model_path() -> Union[str, None]:
        """
        Hack to get path for VMAF model from Homebrew or Linuxbrew.
        This works for libvmaf 2.x

        Returns:
            str or None: the path or None if not found
        """
        stdout, _ = run_command(["brew", "--prefix", "libvmaf"])
        cellar_path = stdout.strip()

        model_path = os.path.join(cellar_path, "share", "libvmaf", "model")

        if not os.path.isdir(model_path):
            logger.warning(
                f"{model_path} does not exist. "
                "Are you sure you have installed the most recent version of libvmaf with Homebrew?"
            )
            return None

        return model_path

    @staticmethod
    def get_default_vmaf_model_path() -> str:
        """
        Return the default model path depending on whether the user is running Homebrew
        or has a static build.

        Returns:
            str: the path
        """
        if has_brew() and ffmpeg_is_from_brew():
            # If the user installed ffmpeg using homebrew
            model_path = FfmpegQualityMetrics.get_brewed_vmaf_model_path()
            if model_path is not None:
                return os.path.join(
                    model_path,
                    "vmaf_v0.6.1.json",
                )

        share_path = os.path.join("/usr", "local", "share", "model")
        if os.path.isdir(share_path):
            return os.path.join(share_path, "vmaf_v0.6.1.json")
        else:
            # return the bundled file as a fallback
            return os.path.join(
                FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY, "vmaf_v0.6.1.json"
            )

    @staticmethod
    def get_supplied_vmaf_models() -> List[str]:
        """
        Return a list of VMAF models supplied with the software.

        Returns:
            List[str]: A list of VMAF model names
        """
        return [
            f
            for f in os.listdir(FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY)
            if f.endswith(".json")
        ]

    def get_global_stats(self) -> GlobalStats:
        """
        Return a dictionary for each calculated metric, with different statstics

        Returns:
            dict: A dictionary with stats, each key being a metric name and each value being a dictionary with the stats for every submetric. The stats are: 'average', 'median', 'stdev', 'min', 'max'.
        """
        for metric_name in self.data:
            logger.debug(f"Aggregating stats for {metric_name}")
            metric_data = cast(SingleMetricData, self.data[metric_name])  # type: ignore
            if len(metric_data) == 0:
                continue
            submetric_keys = [k for k in metric_data[0].keys() if k != "n"]

            stats: Dict[str, GlobalStatsData] = {}
            for submetric_key in submetric_keys:
                values = [float(frame[submetric_key]) for frame in metric_data]
                stats[submetric_key] = {
                    "average": round(float(np.average(values)), 3),
                    "median": round(float(np.median(values)), 3),
                    "stdev": round(float(np.std(values)), 3),
                    "min": round(np.min(values), 3),
                    "max": round(np.max(values), 3),
                }
            self.global_stats[metric_name] = stats  # type: ignore

        return self.global_stats

    def get_results_csv(self) -> str:
        """
        Return a CSV string with the data

        Returns:
            str: The CSV string
        """
        all_dfs = []

        for metric_data in self.data.values():
            if not metric_data:
                continue
            all_dfs.append(pd.DataFrame(cast(SingleMetricData, metric_data)))

        if not all_dfs:
            raise FfmpegQualityMetricsError("No data calculated!")

        try:
            df = reduce(lambda x, y: pd.merge(x, y, on="n"), all_dfs)

            df["input_file_dist"] = self.dist
            df["input_file_ref"] = self.ref

            cols = df.columns.tolist()
            cols.insert(0, cols.pop(cols.index("n")))
            df = df.reindex(columns=cols)
            return df.to_csv(index=False)
        except Exception as e:
            raise FfmpegQualityMetricsError(f"Error merging data to CSV: {e}")

    def get_results_json(self) -> str:
        """
        Return the results as JSON string

        Returns:
            str: The JSON string
        """
        ret: Dict = {}
        for key in self.data:
            metric_data = cast(SingleMetricData, self.data[key])  # type: ignore
            if len(metric_data) == 0:
                continue
            ret[key] = metric_data
        ret["global"] = self.get_global_stats()
        ret["input_file_dist"] = self.dist
        ret["input_file_ref"] = self.ref

        return json.dumps(ret, indent=4)
