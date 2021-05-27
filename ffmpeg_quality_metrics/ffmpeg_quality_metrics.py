# ffmpeg-quality-metrics
# Author: Werner Robitza
# License: MIT

from functools import reduce
import os
import json
import tempfile
import numpy as np
import re
import pandas as pd
from tqdm import tqdm
from ffmpeg_progress_yield import FfmpegProgress

from .utils import (
    NUL,
    ffmpeg_is_from_brew,
    has_brew,
    print_info,
    print_warning,
    run_command,
    win_path_check,
)


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
    DEFAULT_VMAF_THREADS = os.cpu_count()
    DEFAULT_VMAF_MODEL_DIRECTORY = os.path.join(
        os.path.dirname(__file__), "vmaf_models"
    )
    DEFAULT_VMAF_OPTIONS = {
        "n_threads": DEFAULT_VMAF_THREADS,
        "phone_model": False,
        "model_path": None,
    }
    POSSIBLE_FILTERS = ["libvmaf", "psnr", "ssim", "vif"]  # , "identity", "msad"]
    METRIC_TO_FILTER_MAP = {
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
        scaling_algorithm=DEFAULT_SCALER,
        framerate=None,
        dry_run=False,
        verbose=False,
        threads=DEFAULT_THREADS,
        progress=False,
        keep_tmp_files=False,
    ):
        """Instantiate a new FfmpegQualityMetrics

        Args:
            ref (str): reference file
            dist (str): distorted file
            scaling_algorithm (str, optional): A scaling algorithm. Defaults to "bicubic".
            framerate (float, optional): Force a frame rate. Defaults to None.
            dry_run (bool, optional): Don't run anything, just print commands. Defaults to False.
            verbose (bool, optional): Show more output. Defaults to False.
            threads (int, optional): Number of ffmpeg threads. Defaults to 0 (auto).
            progress (bool, optional): Show a progress bar. Defaults to False.
            keep_tmp_files (bool, optional): Keep temporary files for debugging purposes. Defaults to False.

        Raises:
            FfmpegQualityMetricsError: A generic error
        """
        self.ref = str(ref)
        self.dist = str(dist)
        self.scaling_algorithm = str(scaling_algorithm)
        self.framerate = float(framerate) if framerate is not None else None
        self.dry_run = bool(dry_run)
        self.verbose = bool(verbose)
        self.threads = int(threads)
        self.progress = bool(progress)
        self.keep_tmp_files = bool(keep_tmp_files)

        self.data = {
            "vmaf": [],
            "psnr": [],
            "ssim": [],
            "vif": [],
            # "identity": [],
            # "msad": [],
        }

        self.available_filters = []

        self.global_stats = {}

        self.temp_dir = tempfile.gettempdir()
        self.temp_files = {}

        for key in ["psnr", "ssim", "vmaf"]:
            self.temp_files[key] = os.path.join(
                self.temp_dir, next(tempfile._get_candidate_names()) + f"-{key}.txt"
            )
            if self.verbose:
                print_info(
                    f"Writing temporary {key.upper()} information to: {self.temp_files[key]}"
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

        if self.verbose:
            print_info(f"Available filters: {self.available_filters}")

    @staticmethod
    def get_framerate(input_file):
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
            match = pattern.search(str(output)).groups()[0]
            return float(match)
        except Exception:
            raise FfmpegQualityMetricsError(
                f"could not parse FPS from file {input_file}!"
            )

    def _get_framerates(self):
        ref_framerate = FfmpegQualityMetrics.get_framerate(self.ref)
        dist_framerate = FfmpegQualityMetrics.get_framerate(self.dist)

        if ref_framerate != dist_framerate:
            print_warning(
                f"ref, dist framerates differ: {ref_framerate}, {dist_framerate}. "
                "This may result in inaccurate quality metrics. Force an input framerate via the -r option."
            )

        return ref_framerate, dist_framerate

    def _get_filter_opts(self, filter_name):
        """
        Return the specific ffmpeg filter options for a chosen metric filter
        """
        if filter_name in ["ssim", "psnr"]:
            return f"{filter_name}='{win_path_check(self.temp_files[filter_name])}'"
        elif filter_name == "libvmaf":
            return f"libvmaf='{self._get_libvmaf_opts()}'"
        elif filter_name == "vif":
            return "vif,metadata=mode=print"
        else:
            raise FfmpegQualityMetricsError(f"Unknown filter {filter_name}!")

    def calc(self, metrics=["ssim", "psnr"], vmaf_options={}):
        """Calculate one or more metrics.

        Args:
            metrics (list, optional): A list of metrics to calculate.
                Possible values are ["ssim", "psnr", "vmaf"].
                Defaults to ["ssim", "psnr"].
            vmaf_options (dict, optional): VMAF-specific options.
                model_path (str, optional): Path to the VMAF model. Defaults to 0.6.1 model.
                phone_model (bool, optional): Use phone model. Defaults to False.
                n_threads (int, optional): Number of VMAF threads. Defaults to os.cpu_count().
                Defaults to {}.

        Raises:
            FfmpegQualityMetricsError: In case of an error
            e: A generic error

        Returns:
            dict: A dictionary of per-frame info, with the key being the metric name
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
            vmaf_options = {**self.DEFAULT_VMAF_OPTIONS, **vmaf_options}
            self.phone_model = bool(vmaf_options["phone_model"])
            self.n_threads = int(vmaf_options["n_threads"])
            self._set_vmaf_model_path(vmaf_options["model_path"])

        filter_chains = [
            f"[1][0]scale2ref=flags={self.scaling_algorithm}[dist][ref]",
            "[dist]setpts=PTS-STARTPTS[distpts]",
            "[ref]setpts=PTS-STARTPTS[refpts]",
        ]

        # generate split filters depending on the number of models
        n_splits = len(metrics)
        if n_splits > 1:
            for source in ["dist", "ref"]:
                suffixes = "".join([f"[{source}{n}]" for n in range(1, n_splits + 1)])
                filter_chains.extend(
                    [f"[{source}pts]split={n_splits}{suffixes}",]
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
            self._read_ffmpeg_output(output, metrics)
        except Exception as e:
            raise e
        finally:
            self._cleanup_temp_files()

        # return only those data entries containing values
        return {k: v for k, v in self.data.items() if v}

    def _get_libvmaf_opts(self):
        """
        Get a string to use for VMAF in ffmpeg filter chain
        """
        vmaf_opts = {
            "model_path": win_path_check(self.model_path),
            "phone_model": "1" if self.phone_model else "0",
            "log_path": win_path_check(self.temp_files["vmaf"]),
            "log_fmt": "json",
            "psnr": "1",
            "ssim": "1",
            "ms_ssim": "1",
            "n_threads": str(self.n_threads),
        }

        vmaf_opts_string = ":".join(f"{k}={v}" for k, v in vmaf_opts.items())

        return vmaf_opts_string

    def _check_libvmaf_availability(self):
        if "libvmaf" not in self.available_filters:
            raise FfmpegQualityMetricsError(
                "Your ffmpeg build does not have support for VMAF. "
                "Make sure you download or build a version compiled with --enable-libvmaf!"
            )

    def calc_vmaf(
        self, model_path=None, phone_model=False, n_threads=DEFAULT_VMAF_THREADS,
    ):
        """Calculate the VMAF scores for the input files

        Args:
            model_path (str, optional): Path to the VMAF model. Defaults to 0.6.1 model.
            phone_model (bool, optional): Use phone model. Defaults to False.
            n_threads (int, optional): Number of VMAF threads. Defaults to os.cpu_count().

        Raises:
            FfmpegQualityMetricsError: A generic error

        Returns:
            dict: VMAF results
        """
        print_warning(
            "The calc_vmaf() method is deprecated and will be removed eventually. "
            "Please use calc() instead!"
        )

        self._check_libvmaf_availability()

        # map the user-supplied options to the internal attributes
        self.phone_model = bool(phone_model)
        self.n_threads = int(n_threads)
        self._set_vmaf_model_path(model_path)

        filter_chains = [
            f"[1][0]scale2ref=flags={self.scaling_algorithm}[dist][ref]",
            "[dist]setpts=PTS-STARTPTS[distpts]",
            "[ref]setpts=PTS-STARTPTS[refpts]",
            f"[distpts][refpts]{self._get_filter_opts('libvmaf')}",
        ]

        try:
            self._run_ffmpeg_command(filter_chains, desc="VMAF")
            self._read_temp_files(["vmaf"])
        except Exception as e:
            raise e
        finally:
            self._cleanup_temp_files()

        return self.data["vmaf"]

    def _set_vmaf_model_path(self, model_path=None):
        """
        Logic to set the model path depending on the default or the user-supplied string
        """
        if model_path is None:
            self.model_path = FfmpegQualityMetrics.get_default_vmaf_model_path()
        else:
            self.model_path = str(model_path)

        supplied_models = FfmpegQualityMetrics.get_supplied_vmaf_models()

        if not os.path.isfile(self.model_path):
            # check if this is one of the supplied ones? e.g. user passed only a filename
            if self.model_path in supplied_models:
                self.model_path = os.path.join(
                    FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY, self.model_path
                )
            else:
                raise FfmpegQualityMetricsError(
                    f"Could not find model at {self.model_path}. Please set --model-path to a valid VMAF .json model file."
                )

    def _read_vmaf_temp_file(self):
        with open(self.temp_files["vmaf"], "r") as in_vmaf:
            vmaf_log = json.load(in_vmaf)
            for frame_data in vmaf_log["frames"]:
                # append frame number, increase +1
                frame_data["metrics"]["n"] = int(frame_data["frameNum"]) + 1
                self.data["vmaf"].append(frame_data["metrics"])

    def _read_ffmpeg_output(self, ffmpeg_output: str, metrics=[]):
        """
        Read the metric values from ffmpeg's stderr, for those that don't output
        to a file.
        """
        if self.dry_run:
            return
        if "vif" in metrics:
            self._read_vif_output(ffmpeg_output)

    def _read_vif_output(self, ffmpeg_output: str):
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
        frame_data = {}

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

    def _run_ffmpeg_command(self, filter_chains=[], desc=""):
        """
        Run the ffmpeg command to get the quality metrics.
        The filter chains must be specified manually.
        'desc' can be a human readable description for the progress bar.
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
            ff = FfmpegProgress(cmd, self.dry_run)
            with tqdm(total=100, position=1, desc=desc) as pbar:
                for progress in ff.run_command_with_progress():
                    pbar.update(progress - pbar.n)
            return ff.stderr
        else:
            _, stderr = run_command(cmd, self.dry_run, self.verbose)
            return stderr

    def calc_ssim_psnr(self):
        """Calculate SSIM and PSNR

        Raises:
            e: A generic error

        Returns:
            dict: SSIM and PSNR results, each with their own key
        """
        print_warning(
            "The calc_ssim_psnr() method is deprecated and will be removed eventually. "
            "Please use calc() instead!"
        )

        if "ssim" not in self.available_filters:
            raise FfmpegQualityMetricsError(
                "Your ffmpeg build does not have support for the 'ssim' filter. "
            )

        if "psnr" not in self.available_filters:
            raise FfmpegQualityMetricsError(
                "Your ffmpeg build does not have support for the 'psnr' filter. "
            )

        filter_chains = [
            f"[1][0]scale2ref=flags={self.scaling_algorithm}[dist][ref]",
            "[dist]setpts=PTS-STARTPTS[distpts]",
            "[ref]setpts=PTS-STARTPTS[refpts]",
            "[distpts]split[dist1][dist2]",
            "[refpts]split[ref1][ref2]",
            f"[dist1][ref1]{self._get_filter_opts('ssim')}",
            f"[dist2][ref2]{self._get_filter_opts('psnr')}",
        ]

        try:
            self._run_ffmpeg_command(filter_chains, desc="PSNR and SSIM")
            self._read_temp_files(["ssim", "psnr"])
        except Exception as e:
            raise e
        finally:
            self._cleanup_temp_files()

        return {"ssim": self.data["ssim"], "psnr": self.data["psnr"]}

    def _cleanup_temp_files(self):
        if self.keep_tmp_files:
            return
        for temp_file in self.temp_files.values():
            if os.path.isfile(temp_file):
                os.remove(temp_file)

    def _read_psnr_temp_file(self):
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

    def _read_ssim_temp_file(self):
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
    def get_brewed_vmaf_model_path():
        """
        Hack to get path for VMAF model from Linuxbrew

        Returns:
            str: the path
        """
        stdout, _ = run_command(["brew", "--prefix", "libvmaf"])
        cellar_path = stdout.strip()

        model_path = os.path.join(cellar_path, "share", "model")

        return model_path

    @staticmethod
    def get_default_vmaf_model_path():
        """
        Return the default model path depending on whether the user is running Homebrew
        or has a static build.

        Returns:
            str: the path
        """
        if has_brew() and ffmpeg_is_from_brew():
            # If the user installed ffmpeg using homebrew
            return os.path.join(
                # FIXME: change this once VMAF 2.0 is bundled with homebrew!
                FfmpegQualityMetrics.get_brewed_vmaf_model_path(),
                "vmaf_v0.6.1.pkl",
            )
        else:
            # return the bundled file as a fallback
            return os.path.join(
                os.path.dirname(__file__), "vmaf_models", "vmaf_v0.6.1.json"
            )

    @staticmethod
    def get_supplied_vmaf_models():
        """
        Return a list of VMAF models supplied with the software.

        Returns:
            list: A list of VMAF model names
        """
        return os.listdir(FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY)

    def get_global_stats(self):
        """
        Return a dictionary for each calculated metric, with different statstics

        Returns:
            dict: A dictionary with stats
        """
        for metric_name, metric_data in self.data.items():
            if len(metric_data) == 0:
                continue

            # which value to access?
            if metric_name in ["ssim", "psnr"]:
                value_key = metric_name + "_avg"
            elif metric_name == "vmaf":
                value_key = "vmaf"
            elif metric_name == "vif":
                value_key = "scale_0"

            values = [float(entry[value_key]) for entry in metric_data]
            self.global_stats[metric_name] = {
                "average": round(np.average(values), 3),
                "median": round(np.median(values), 3),
                "stdev": round(np.std(values), 3),
                "min": round(np.min(values), 3),
                "max": round(np.max(values), 3),
            }

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
            all_dfs.append(pd.DataFrame(metric_data))

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
        ret = {}
        for key, metric_data in self.data.items():
            if len(metric_data) == 0:
                continue
            ret[key] = metric_data
        ret["global"] = self.get_global_stats()
        ret["input_file_dist"] = self.dist
        ret["input_file_ref"] = self.ref

        return json.dumps(ret, indent=4)
