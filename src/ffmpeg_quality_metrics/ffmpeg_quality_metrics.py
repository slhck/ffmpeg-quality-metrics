# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

from io import StringIO
import json
import logging
import math
import os
import re
import tempfile
import csv
from fractions import Fraction
from typing import Dict, List, Literal, Tuple, TypedDict, Union, cast
from os import devnull as NUL

from ffmpeg_progress_yield import FfmpegProgress
from tqdm import tqdm
from statistics import median, pstdev, mean

from .utils import (
    ffmpeg_is_from_brew,
    get_ffprobe_path,
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
    ten_bit: bool
    """
    Convert both inputs to 10 bit (yuv420p10le) before calculating VMAF.
    Recommended for VMAF v1 models, which should ideally be applied at 10-bit precision for SDR content.
    Defaults to False.
    """


MetricName = Literal["psnr", "ssim", "vmaf", "vif", "msad"]
"""The name of a metric."""

FilterName = Literal["psnr", "ssim", "libvmaf", "vif", "msad"]
"""The name of an ffmpeg filter used for that metric."""

SingleMetricData = List[Dict[str, float]]
"""A per-frame list of metric values."""

GlobalStatsData = Dict[str, float]
"""A dict of global stats for a metric."""

GlobalStats = Dict[MetricName, Dict[str, GlobalStatsData]]
"""A dict of global stats for all metrics."""

MetricData = Dict[MetricName, SingleMetricData]
"""A dict of per-frame metric values for all metrics."""


class InputInfo(TypedDict):
    """
    Properties of the first video stream of an input file, as reported by ffprobe.
    """

    path: str
    """Path to the input file."""
    width: int
    """Width in pixels."""
    height: int
    """Height in pixels."""
    framerate: Union[float, None]
    """Frame rate in frames per second, or None if unknown."""
    duration: Union[float, None]
    """Duration in seconds, or None if unknown."""
    nb_frames: Union[int, None]
    """Number of frames from the container metadata, or None if unknown."""


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
        "ten_bit": False,
    }
    POSSIBLE_FILTERS: List[FilterName] = [
        "libvmaf",
        "psnr",
        "ssim",
        "vif",
        "msad",
    ]
    METRIC_TO_FILTER_MAP: Dict[MetricName, FilterName] = {
        "vmaf": "libvmaf",
        "psnr": "psnr",
        "ssim": "ssim",
        "vif": "vif",
        "msad": "msad",
    }
    SUMMARY_SUBMETRICS: Dict[MetricName, List[str]] = {
        "psnr": ["psnr_avg"],
        "ssim": ["ssim_avg"],
        "vmaf": ["vmaf"],
        "vif": ["scale_0", "scale_1", "scale_2", "scale_3"],
        "msad": ["msad_avg"],
    }
    """Main submetrics of each metric, shown in the summary from `get_summary()`."""

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
        num_frames: Union[int, None] = None,
        start_offset: Union[str, None] = None,
        ffmpeg_path: str = "ffmpeg",
    ):
        """Instantiate a new FfmpegQualityMetrics

        Args:
            ref (str): reference file
            dist (str): distorted file
            scaling_algorithm (str, optional): A scaling algorithm. Must be one of the following: ["fast_bilinear", "bilinear", "bicubic", "experimental", "neighbor", "area", "bicublin", "gauss", "sinc", "lanczos", "spline"]. Defaults to "bicubic"
            framerate (float, optional): Force a frame rate. Defaults to None.
            dist_delay (float): Temporally align the distorted file against the reference by this many seconds, by trimming the leading unmatched frames of one stream before comparison. A positive value means the distorted stream starts this many seconds after the reference (the reference's leading frames are trimmed); a negative value means the distorted stream leads (its leading frames are trimmed). Defaults to 0.
            dry_run (bool, optional): Don't run anything, just print commands. Defaults to False.
            verbose (bool, optional): Show more output. Defaults to False.
            threads (int, optional): Number of ffmpeg threads. Defaults to 0 (auto).
            progress (bool, optional): Show a progress bar. Defaults to False.
            keep_tmp_files (bool, optional): Keep temporary files for debugging purposes. Defaults to False.
            tmp_dir (str, optional): Directory to store temporary files. Will use system default if not specified. Defaults to None.
            num_frames (int, optional): Number of frames to analyze from the input files. Defaults to None (all frames).
            start_offset (str, optional): Seek to this position before analyzing. Accepts timestamp (e.g., '00:00:10' or '10.5') or frame number with 'f:' prefix (e.g., 'f:100'). Defaults to None.
            ffmpeg_path (str, optional): Path to ffmpeg executable. Defaults to "ffmpeg".

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
        self.num_frames = int(num_frames) if num_frames is not None else None
        self.start_offset = str(start_offset) if start_offset is not None else None
        self.ffmpeg_path = ffmpeg_path

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
            "msad": [],
        }

        self.available_filters: List[str] = []

        self.global_stats: GlobalStats = {}

        self.input_info: Union[Tuple[InputInfo, InputInfo], None] = None
        """Properties of the reference and distorted file, set by `check_inputs()`."""
        self._inputs_checked = False

        if not os.path.isdir(self.tmp_dir):
            logger.debug(f"Creating temporary directory: {self.tmp_dir}")
            os.makedirs(self.tmp_dir)
        self.temp_files: Dict[FilterName, str] = {}

        for filter_name in self.POSSIBLE_FILTERS:
            suffix = "txt" if filter_name != "libvmaf" else "json"

            self.temp_files[filter_name] = os.path.join(
                self.tmp_dir,
                f"ffmpeg_quality_metrics_{filter_name}_{os.path.basename(self.ref)}_{os.path.basename(self.dist)}.{suffix}",
            )
            logger.debug(
                f"Writing temporary {filter_name.upper()} information to: {self.temp_files[filter_name]}"
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
        cmd = [self.ffmpeg_path, "-filters"]
        try:
            stdout, _ = run_command(cmd)
        except OSError as e:
            raise FfmpegQualityMetricsError(
                f"Could not run ffmpeg at '{self.ffmpeg_path}': {e.strerror}. "
                "Check the path to ffmpeg (--ffmpeg-path)."
            ) from e
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
    def get_framerate(input_file: str, ffmpeg_path: str = "ffmpeg") -> float:
        """Parse the FPS from the input file.

        First parse it from the ffmpeg banner ("<n> fps"). Some container/codec
        combinations (e.g. FFV1 in a .nut) do not print an fps token in the
        banner (only "tbr"/"tbn"), so fall back to querying ffprobe for the
        exact rational frame rate. ffprobe ships with ffmpeg, so this adds no
        new dependency.

        Args:
            input_file (str): Input file path
            ffmpeg_path (str, optional): Path to ffmpeg executable. Defaults to "ffmpeg".

        Raises:
            FfmpegQualityMetricsError: A generic error

        Returns:
            float: The FPS parsed
        """
        cmd = [ffmpeg_path, "-nostdin", "-y", "-i", input_file]

        output = run_command(cmd, allow_error=True)
        pattern = re.compile(r"(\d+(\.\d+)?) fps")
        try:
            if pattern_ret := pattern.search(str(output)):
                match = pattern_ret.groups()[0]
                return float(match)
        except Exception:
            pass

        # Fallback: the ffmpeg banner did not contain an "<n> fps" token (this
        # happens for some container/codec combinations, e.g. FFV1 in .nut,
        # which only report "tbr"/"tbn"). Query ffprobe for the exact rational
        # frame rate instead of failing. Prefer r_frame_rate, then
        # avg_frame_rate; skip missing/"0/0" values.
        ffprobe_path = get_ffprobe_path(ffmpeg_path)
        for field in ("r_frame_rate", "avg_frame_rate"):
            try:
                stdout, _ = run_command(
                    [
                        ffprobe_path,
                        "-loglevel",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        f"stream={field}",
                        "-of",
                        "csv=p=0",
                        input_file,
                    ],
                    allow_error=True,
                )
            except Exception:
                continue
            value = stdout.strip().splitlines()[0].strip() if stdout.strip() else ""
            if not value or value == "0/0":
                continue
            try:
                frac = Fraction(value)
            except (ValueError, ZeroDivisionError):
                continue
            if frac > 0:
                return float(frac)

        raise FfmpegQualityMetricsError(f"could not parse FPS from file {input_file}!")

    def _get_framerates(self) -> Tuple[float, float]:
        """
        Get the framerates of the reference and distorted files.

        Returns:
            Tuple[float, float]: The framerates of the reference and distorted files
        """
        ref_framerate = FfmpegQualityMetrics.get_framerate(self.ref, self.ffmpeg_path)
        dist_framerate = FfmpegQualityMetrics.get_framerate(self.dist, self.ffmpeg_path)

        # check_inputs() already warns about differing frame rates
        if ref_framerate != dist_framerate and self.input_info is None:
            logger.warning(
                f"ref, dist framerates differ: {ref_framerate}, {dist_framerate}. "
                "This may result in inaccurate quality metrics. Force an input framerate via the -r option."
            )

        return ref_framerate, dist_framerate

    @staticmethod
    def probe_input(input_file: str, ffmpeg_path: str = "ffmpeg") -> InputInfo:
        """Read the properties of the first video stream of a file with ffprobe.

        ffprobe is expected next to the ffmpeg executable, or in the PATH.

        Args:
            input_file (str): Input file path
            ffmpeg_path (str, optional): Path to ffmpeg executable. Defaults to "ffmpeg".

        Raises:
            FfmpegQualityMetricsError: If the file does not exist, cannot be read, or has no video stream
            FileNotFoundError: If ffprobe cannot be found

        Returns:
            InputInfo: The video stream properties
        """
        if not os.path.isfile(input_file):
            raise FfmpegQualityMetricsError(f"File not found: {input_file}")

        cmd = [
            get_ffprobe_path(ffmpeg_path),
            "-loglevel",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,avg_frame_rate,duration,nb_frames"
            ":format=duration",
            "-of",
            "json",
            input_file,
        ]
        try:
            stdout, _ = run_command(cmd)
            probe_data = json.loads(stdout)
        except (RuntimeError, ValueError) as e:
            # the last line of ffprobe's error output names the problem
            detail = str(e).strip().splitlines()[-1] if str(e).strip() else ""
            raise FfmpegQualityMetricsError(
                f"Could not read file {input_file} with ffprobe: {detail}"
            ) from e

        streams = probe_data.get("streams") or []
        if not streams:
            raise FfmpegQualityMetricsError(f"No video stream found in {input_file}")
        stream = streams[0]

        framerate = None
        for field in ("r_frame_rate", "avg_frame_rate"):
            try:
                frac = Fraction(stream.get(field, ""))
            except (ValueError, ZeroDivisionError):
                continue
            if frac > 0:
                framerate = float(frac)
                break

        duration = None
        for value in (
            stream.get("duration"),
            probe_data.get("format", {}).get("duration"),
        ):
            try:
                duration = float(value)
                break
            except (TypeError, ValueError):
                continue

        try:
            nb_frames = int(stream["nb_frames"])
        except (KeyError, TypeError, ValueError):
            nb_frames = None

        return {
            "path": input_file,
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "framerate": framerate,
            "duration": duration,
            "nb_frames": nb_frames,
        }

    def check_inputs(self) -> Union[Tuple[InputInfo, InputInfo], None]:
        """Probe both input files and log a warning for each property that differs.

        Compares resolution, frame rate, and duration (or frame count). This is run
        automatically before the first calculation.

        Raises:
            FfmpegQualityMetricsError: If an input cannot be read or has no video stream

        Returns:
            Tuple[InputInfo, InputInfo] or None: The properties of the reference and distorted file,
                or None if ffprobe is not available
        """
        try:
            ref_info = FfmpegQualityMetrics.probe_input(self.ref, self.ffmpeg_path)
            dist_info = FfmpegQualityMetrics.probe_input(self.dist, self.ffmpeg_path)
        except FileNotFoundError:
            logger.warning(
                f"ffprobe not found at {get_ffprobe_path(self.ffmpeg_path)}, skipping input checks"
            )
            return None

        logger.debug(f"Reference input: {ref_info}")
        logger.debug(f"Distorted input: {dist_info}")

        self._check_resolution(ref_info, dist_info)
        self._check_framerate(ref_info, dist_info)
        self._check_duration(ref_info, dist_info)

        self.input_info = (ref_info, dist_info)
        return self.input_info

    def _check_resolution(self, ref_info: InputInfo, dist_info: InputInfo) -> None:
        """
        Warn if the resolutions differ.
        """
        ref_res = f"{ref_info['width']}x{ref_info['height']}"
        dist_res = f"{dist_info['width']}x{dist_info['height']}"
        if ref_res != dist_res:
            logger.warning(
                f"Resolutions differ: distorted {dist_res}, reference {ref_res}. "
                f"The distorted video will be scaled to {ref_res} "
                f"({self.scaling_algorithm}) before comparison, "
                "which affects the metric values."
            )

    def _check_framerate(self, ref_info: InputInfo, dist_info: InputInfo) -> None:
        """
        Warn if the frame rates differ and no frame rate is forced.
        """
        ref_fps = ref_info["framerate"]
        dist_fps = dist_info["framerate"]
        if ref_fps is None or dist_fps is None or self.framerate is not None:
            return
        if not math.isclose(ref_fps, dist_fps, abs_tol=1e-3):
            logger.warning(
                f"Frame rates differ: distorted {dist_fps:g} fps, reference {ref_fps:g} fps. "
                "Frames will not line up in time, so the metrics will be inaccurate. "
                "Convert both inputs to the same frame rate, or force one with the -r option."
            )

    def _check_duration(self, ref_info: InputInfo, dist_info: InputInfo) -> None:
        """
        Warn if the inputs differ in length, after applying dist_delay.
        Skipped if num_frames is set.
        """
        if self.num_frames is not None:
            return

        ref_frames = ref_info["nb_frames"]
        dist_frames = dist_info["nb_frames"]
        ref_fps = ref_info["framerate"]
        dist_fps = dist_info["framerate"]
        # frame counts are only comparable if frames are paired one by one
        same_framerate = self.framerate is not None or (
            ref_fps is not None
            and dist_fps is not None
            and math.isclose(ref_fps, dist_fps, abs_tol=1e-3)
        )
        if (
            self.dist_delay == 0
            and same_framerate
            and ref_frames is not None
            and dist_frames is not None
        ):
            if ref_frames != dist_frames:
                longer = "reference" if ref_frames > dist_frames else "distorted"
                logger.warning(
                    f"Frame counts differ: distorted {dist_frames}, reference {ref_frames}. "
                    f"Only the first {min(ref_frames, dist_frames)} frames are compared; "
                    f"the remaining frames of the {longer} video are ignored."
                )
            return

        ref_duration = ref_info["duration"]
        dist_duration = dist_info["duration"]
        if ref_duration is None or dist_duration is None:
            return

        # dist_delay trims the start of one of the inputs
        ref_duration = max(ref_duration - max(self.dist_delay, 0), 0)
        dist_duration = max(dist_duration - max(-self.dist_delay, 0), 0)

        # tolerate a difference of one frame
        known_fps = [
            fps
            for fps in (self.framerate, ref_info["framerate"], dist_info["framerate"])
            if fps
        ]
        tolerance = 1 / min(known_fps) if known_fps else 0.05

        if abs(ref_duration - dist_duration) > tolerance + 1e-6:
            longer = "reference" if ref_duration > dist_duration else "distorted"
            delay_note = (
                f" (after trimming {abs(self.dist_delay):g} s for the distortion delay)"
                if self.dist_delay != 0
                else ""
            )
            logger.warning(
                f"Durations differ{delay_note}: distorted {dist_duration:.3f} s, "
                f"reference {ref_duration:.3f} s. "
                f"Only the first {min(ref_duration, dist_duration):.3f} s are compared; "
                f"the rest of the {longer} video is ignored."
            )

    def _parse_start_offset(self, framerate: float) -> Union[str, None]:
        """
        Parse the start_offset parameter and convert frame numbers to timestamps if needed.

        Args:
            framerate (float): The framerate to use for frame-to-timestamp conversion

        Returns:
            Union[str, None]: The timestamp string for ffmpeg's -ss option, or None if no offset
        """
        if self.start_offset is None:
            return None

        # Check if it's a frame number (format: "f:100" or "f:100.5")
        if self.start_offset.startswith("f:"):
            try:
                frame_num = float(self.start_offset[2:])
                timestamp = frame_num / framerate
                return str(timestamp)
            except ValueError:
                raise FfmpegQualityMetricsError(
                    f"Invalid frame number in start_offset: {self.start_offset}"
                )

        # Otherwise, assume it's a timestamp string (e.g., "00:00:10" or "10.5")
        return self.start_offset

    def _get_filter_opts(self, filter_name: FilterName) -> str:
        """
        Returns:
            str: Specific ffmpeg filter options for a chosen metric filter.
        """
        framesync_opts = "shortest=1:repeatlast=0"

        if filter_name in ["ssim", "psnr"]:
            return (
                f"{filter_name}='{win_path_check(self.temp_files[filter_name])}'"
                f":{framesync_opts}"
            )
        elif filter_name == "libvmaf":
            return f"libvmaf='{self._get_libvmaf_filter_opts()}'"
        elif filter_name == "vif":
            return f"vif={framesync_opts},metadata=mode=print"
        elif filter_name == "msad":
            return f"msad={framesync_opts},metadata=mode=print"
        else:
            raise FfmpegQualityMetricsError(f"Unknown filter {filter_name}!")

    def _get_metric_filter_chains(
        self, metric_name: MetricName, dist_label: str, ref_label: str
    ) -> List[str]:
        """
        Build the filter chain(s) for a single metric, reading from the given
        distorted and reference filter graph labels.

        Returns:
            List[str]: One or more filter chains
        """
        chains: List[str] = []

        # convert both inputs to 10 bit if requested, as recommended for VMAF v1 models
        if metric_name == "vmaf" and self.vmaf_options["ten_bit"]:
            chains.extend(
                [
                    f"[{dist_label}]format=yuv420p10le[{dist_label}10b]",
                    f"[{ref_label}]format=yuv420p10le[{ref_label}10b]",
                ]
            )
            dist_label += "10b"
            ref_label += "10b"

        chains.append(
            f"[{dist_label}][{ref_label}]{self._get_filter_opts(self.METRIC_TO_FILTER_MAP[metric_name])}"
        )
        return chains

    def calculate(
        self,
        metrics: Union[List[MetricName], None] = None,
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
        if metrics is None:
            metrics = ["ssim", "psnr"]
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

        # probe the inputs once, before running ffmpeg
        if not self._inputs_checked:
            self.check_inputs()
            self._inputs_checked = True

        # set VMAF options specifically
        if "vmaf" in metrics:
            self._check_libvmaf_availability()
            self.vmaf_options = self.DEFAULT_VMAF_OPTIONS.copy()
            # override with user-supplied options
            if vmaf_options:
                for key, value in vmaf_options.items():
                    if value is not None:
                        self.vmaf_options[key] = value  # type: ignore
            self._set_vmaf_model_path(self.vmaf_options["model_path"])

        # ffmpeg 7.1 or higher: scale2ref filter is deprecated
        # input 0: ref, input 1: dist --> swapped for scale filter

        # Apply select filter if num_frames is specified
        select_filter = ""
        if self.num_frames is not None:
            select_filter = f"select='lt(n\\,{self.num_frames})',"

        # Apply dist_delay by trimming the leading, unmatched portion of one
        # stream so the two streams are temporally aligned before comparison.
        # libvmaf (and the other metric filters) pair frames sequentially, so a
        # PTS-only shift (e.g. -itsoffset) is cancelled by the setpts reset below
        # and has no effect. Trimming happens at decode time - no re-encode.
        # dist_delay > 0: distorted is delayed against the reference, so the
        #   reference has extra leading frames -> trim the reference.
        # dist_delay < 0: the distorted stream leads -> trim the distorted.
        ref_trim = f"trim=start={self.dist_delay}," if self.dist_delay > 0 else ""
        dist_trim = f"trim=start={abs(self.dist_delay)}," if self.dist_delay < 0 else ""

        # Align both streams before the reference is split between the scale
        # filter and the metric filter. Feeding the untrimmed reference directly
        # to scale while separately trimming it for the metric makes ffmpeg
        # buffer the entire skipped lead-in on large positive delays. Real
        # captures can start tens of seconds into a source, which previously
        # grew memory into gigabytes and could be OOM-killed.
        filter_chains = [
            f"[0]{ref_trim}{select_filter}settb=AVTB,setpts=PTS-STARTPTS[refaligned]",
            "[refaligned]split=2[refscale][refpts]",
            f"[1]{dist_trim}{select_filter}settb=AVTB,setpts=PTS-STARTPTS[distaligned]",
            f"[distaligned][refscale]scale=rw:rh:flags={self.scaling_algorithm}[distpts]",
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
            filter_chains.extend(
                self._get_metric_filter_chains(metrics[0], "distpts", "refpts")
            )
        # all other cases:
        else:
            for n, metric_name in zip(range(1, n_splits + 1), metrics):
                filter_chains.extend(
                    self._get_metric_filter_chains(metric_name, f"dist{n}", f"ref{n}")
                )

        # drop results of earlier calls to avoid accumulate metrics
        # rebind (instead of clearing) so previously returned results stay intact
        for metric_name in metrics:
            self.data[metric_name] = []
        self.global_stats = {}

        try:
            output = self._run_ffmpeg_command(filter_chains, desc=", ".join(metrics))
            if self.dry_run:
                return {}
            self._read_temp_files(metrics)
            if output:
                self._read_ffmpeg_output(output, metrics)
            else:
                raise FfmpegQualityMetricsError("ffmpeg output is empty!")
        except RuntimeError as e:
            if "could not initialize feature extractor" in str(e):
                raise FfmpegQualityMetricsError(
                    "Your ffmpeg build is linked against a libvmaf version that does not support "
                    "one of the features required by the chosen VMAF model. "
                    "VMAF v1 models (vmaf_v1.0.16 and newer) require libvmaf 3.2.1 or newer. "
                    f"Original error:\n{e}"
                ) from e
            raise
        finally:
            self._cleanup_temp_files()

        # return only those data entries containing values
        return {k: v for k, v in self.data.items() if v}

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
            # Terminate at the shorter of the two aligned streams. libvmaf is a
            # framesync filter whose default (shortest=0, repeatlast=1) repeats
            # the last frame of the shorter stream until the longer one ends.
            # After dist_delay trims the leading frames to align the starts, the
            # reference is typically still longer than the distorted clip (e.g. a
            # full-length source vs a short recording); without shortest=1 those
            # trailing reference frames are compared against a frozen distorted
            # frame, cratering the pooled score. Compare only the overlap.
            "shortest": "1",
            "repeatlast": "0",
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
                "Your ffmpeg build does not have support for VMAF. Make sure you download or build a version compiled with --enable-libvmaf!"
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
                    f"Could not find model at {self.vmaf_model_path}. Please set --model-path to a valid VMAF .json model file."
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

    def _read_ffmpeg_output(
        self, ffmpeg_output: str, metrics: List[MetricName]
    ) -> None:
        """
        Read the metric values from ffmpeg's stderr, for those that don't output
        to a file.
        """
        if self.dry_run:
            return
        if "vif" in metrics:
            self._parse_ffmpeg_metadata_output(ffmpeg_output, "vif")
        if "msad" in metrics:
            self._parse_ffmpeg_metadata_output(ffmpeg_output, "msad")

    def _parse_ffmpeg_metadata_output(
        self, ffmpeg_output: str, metric_name: Literal["vif", "msad"]
    ) -> None:
        """
        Parse the filter output written to ffmpeg's metadata output

        Args:
            ffmpeg_output (str): The output of ffmpeg's stderr
            metric_name (Literal["vif", "msad"]): The name of the metric to parse
        """
        # Example for VIF:
        #
        # [Parsed_metadata_4 @ 0x7f995cd08640] frame:1    pts:1       pts_time:0.0401x
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.0=0.263582
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.1=0.560129
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.2=0.626596
        # [Parsed_metadata_4 @ 0x7f995cd08640] lavfi.vif.scale.3=0.682183
        #
        # Example for MSAD:
        #
        # [Parsed_metadata_6 @ 0x10ad04ea0] lavfi.msad.msad.Y=0.029998
        # [Parsed_metadata_6 @ 0x10ad04ea0] lavfi.msad.msad.U=0.019501
        # [Parsed_metadata_6 @ 0x10ad04ea0] lavfi.msad.msad.V=0.026455
        # [Parsed_metadata_6 @ 0x10ad04ea0] lavfi.msad.msad_avg=0.025318

        # Each metadata filter instance (e.g. "[Parsed_metadata_4") prints its own
        # "frame:" lines, and the output of several instances is interleaved.
        # Collect the frames per instance, then keep only the instances that
        # printed values for this metric.
        frames_by_instance: Dict[str, List[Dict[str, float]]] = {}
        metric_instances: List[str] = []
        metric_prefix = f"lavfi.{metric_name}."

        for line in ffmpeg_output.split("\n"):
            line = line.strip()
            if not line.startswith("[Parsed_metadata"):
                continue

            fields = line.split(" ")
            if len(fields) < 4:
                continue
            instance, entry = fields[0], fields[3]

            # a new frame appears
            if entry.startswith("frame:"):
                # the metadata filter counts from 0, all other metrics count from 1
                frame_data: Dict[str, float] = {"n": int(entry.split(":")[1]) + 1}
                frames_by_instance.setdefault(instance, []).append(frame_data)
                continue

            # no frame was set, or no info for this metric
            if instance not in frames_by_instance or not entry.startswith(
                metric_prefix
            ):
                continue

            if instance not in metric_instances:
                metric_instances.append(instance)

            key, value = entry.split("=")
            key = key.replace(metric_prefix, "").replace(".", "_").lower()
            frames_by_instance[instance][-1][key] = round(float(value), 3)

        for instance in metric_instances:
            self.data[metric_name].extend(frames_by_instance[instance])

    def _read_temp_files(self, metrics: List[MetricName]) -> None:
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
        self, filter_chains: List[str], desc: str = ""
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

        # Parse start_offset
        start_offset_timestamp = self._parse_start_offset(ref_framerate)

        cmd = [
            self.ffmpeg_path,
            "-nostdin",
            "-nostats",
            "-y",
            "-threads",
            str(self.threads),
        ]

        # Add -ss before reference input if start_offset is specified
        if start_offset_timestamp is not None:
            cmd.extend(["-ss", start_offset_timestamp])

        # Add -r before -i only if no start_offset (to avoid seeking issues)
        # When seeking is used, -r before -i can interfere with frame-accurate seeking
        if start_offset_timestamp is None:
            cmd.extend(["-r", str(ref_framerate)])

        # Note: dist_delay is applied via a trim filter in the filter graph (see
        # calculate), not via -itsoffset. A PTS shift here would be cancelled by
        # the setpts=PTS-STARTPTS reset and would not align the streams.
        cmd.extend(["-i", self.ref])

        # Add -ss before distorted input if start_offset is specified
        if start_offset_timestamp is not None:
            cmd.extend(["-ss", start_offset_timestamp])

        # Add -r before -i only if no start_offset
        if start_offset_timestamp is None:
            cmd.extend(["-r", str(dist_framerate)])

        cmd.extend(
            [
                "-i",
                self.dist,
                "-filter_complex",
                ";".join(filter_chains),
                "-an",
                "-f",
                "null",
                NUL,
            ]
        )

        if self.dry_run:
            print(quoted_cmd(cmd))
            return ""

        if self.progress:
            logger.debug(quoted_cmd(cmd))
            with FfmpegProgress(cmd, self.dry_run) as ff:
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
                f"{model_path} does not exist. Are you sure you have installed the most recent version of libvmaf with Homebrew?"
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
        return sorted(
            f
            for f in os.listdir(FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY)
            if f.endswith(".json")
        )

    def get_global_stats(self) -> GlobalStats:
        """
        Return a dictionary for each calculated metric, with different statstics

        Returns:
            dict: A dictionary with stats, each key being a metric name and each value being a dictionary with the stats for every submetric. The stats are: 'average', 'median', 'stdev', 'min', 'max'.
        """
        for metric_name in self.data:
            logger.debug(f"Aggregating stats for {metric_name}")
            metric_data = self.data[metric_name]
            if len(metric_data) == 0:
                continue
            submetric_keys = [k for k in metric_data[0].keys() if k != "n"]

            stats: Dict[str, GlobalStatsData] = {}
            for submetric_key in submetric_keys:
                values = [float(frame[submetric_key]) for frame in metric_data]
                # Filter out non-finite values (inf, -inf, nan) for robust statistics
                finite = [v for v in values if math.isfinite(v)]
                # Fallback to [0.0] if all values are non-finite to prevent crashes
                all_values = finite if finite else [0.0]

                stats[submetric_key] = {
                    "average": round(float(mean(all_values)), 3),
                    "median": round(float(median(all_values)), 3),
                    "stdev": round(
                        float(pstdev(finite)) if len(finite) > 1 else 0.0, 3
                    ),
                    "min": round(min(all_values), 3),
                    "max": round(max(all_values), 3),
                }
            self.global_stats[metric_name] = stats

        return self.global_stats

    def get_summary(self) -> str:
        """
        Return a short, human-readable table of the global stats (average, min, max)
        for the main submetric of each calculated metric.

        The main submetrics are defined in `SUMMARY_SUBMETRICS`. If a metric has none of them,
        all of its submetrics are listed.

        Returns:
            str: The summary table, or an empty string if no data was calculated
        """
        global_stats = self.get_global_stats()
        if not global_stats:
            return ""

        rows: List[Tuple[str, GlobalStatsData]] = []
        for metric_name, metric_stats in global_stats.items():
            main_keys = [
                k
                for k in self.SUMMARY_SUBMETRICS.get(metric_name, [])
                if k in metric_stats
            ]
            for key in main_keys or list(metric_stats.keys()):
                label = key if key.startswith(metric_name) else f"{metric_name}_{key}"
                rows.append((label, metric_stats[key]))

        n_frames = max(len(frames) for frames in self.data.values())
        label_width = max(len("metric"), *(len(label) for label, _ in rows))

        lines = [
            f"Summary over {n_frames} frame{'s' if n_frames != 1 else ''}:",
            f"  {'metric':<{label_width}} {'average':>10} {'min':>10} {'max':>10}",
        ]
        for label, stats in rows:
            lines.append(
                f"  {label:<{label_width}} {stats['average']:>10.3f}"
                f" {stats['min']:>10.3f} {stats['max']:>10.3f}"
            )
        return "\n".join(lines)

    def get_results_csv(self) -> str:
        """
        Return a CSV string with the data

        Returns:
            str: The CSV string
        """
        # Check if we have any data
        has_data = any(metric_data for metric_data in self.data.values())
        if not has_data:
            raise FfmpegQualityMetricsError("No data calculated!")

        # Collect all frames and merge data by frame number
        frames_data: Dict[int, Dict[str, Union[str, float, int]]] = {}

        # Process each metric's data
        for metric_data in self.data.values():
            if not metric_data:
                continue

            for frame_info in cast(SingleMetricData, metric_data):
                frame_num = int(frame_info["n"])
                if frame_num not in frames_data:
                    frames_data[frame_num] = {"n": frame_num}

                # Add all metric properties for this frame
                for key, value in frame_info.items():
                    if key != "n":  # Skip frame number as it's already added
                        frames_data[frame_num][key] = value

        if not frames_data:
            raise FfmpegQualityMetricsError("No frame data found!")

        # Sort frames by frame number
        sorted_frames = sorted(frames_data.keys())

        # Collect all unique column names (excluding 'n' which we'll put first)
        all_columns: set[str] = set()
        for frame_data in frames_data.values():
            all_columns.update(frame_data.keys())
        all_columns.discard("n")

        # Create column order: n first, then sorted metric columns, then input files
        columns = ["n"] + sorted(all_columns) + ["input_file_dist", "input_file_ref"]

        # Generate CSV using StringIO and csv module
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(columns)

        # Write data rows
        for frame_num in sorted_frames:
            frame_data = frames_data[frame_num]
            row = []
            for col in columns:
                if col == "input_file_dist":
                    row.append(self.dist)
                elif col == "input_file_ref":
                    row.append(self.ref)
                else:
                    # Use the frame data value or empty string if not present
                    row.append(str(frame_data.get(col, "")))
            writer.writerow(row)

        return output.getvalue()

    def get_results_json(self) -> str:
        """
        Return the results as JSON string

        Returns:
            str: The JSON string
        """
        ret: Dict = {}
        for key in self.data:
            metric_data = self.data[key]
            if len(metric_data) == 0:
                continue
            ret[key] = metric_data
        ret["global"] = self.get_global_stats()
        ret["input_file_dist"] = self.dist
        ret["input_file_ref"] = self.ref

        return json.dumps(ret, indent=4)
