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

    def __init__(
        self,
        ref: str,
        dist: str,
        scaling_algorithm=DEFAULT_SCALER,
        framerate=None,
        dry_run=False,
        verbose=False,
        threads=DEFAULT_THREADS,
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

        self.vmaf_data = []
        self.psnr_data = []
        self.ssim_data = []

        self.global_stats = {}

        self.temp_dir = tempfile.gettempdir()
        self.temp_files = {}
        for key in ["psnr", "ssim", "vmaf"]:
            self.temp_files[key] = os.path.join(
                self.temp_dir, next(tempfile._get_candidate_names()) + f"-{key}.txt"
            )

        if scaling_algorithm not in self.ALLOWED_SCALERS:
            raise FfmpegQualityMetricsError(
                f"Allowed scaling algorithms: {self.ALLOWED_SCALERS}"
            )

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

    def calc_vmaf(
        self,
        model_path=None,
        phone_model=False,
        n_threads=os.cpu_count(),
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
        self.phone_model = bool(phone_model)

        if model_path is None:
            self.model_path = FfmpegQualityMetrics.get_default_vmaf_model_path()
        else:
            self.model_path = str(model_path)
        self.n_threads = int(n_threads)

        supplied_models = FfmpegQualityMetrics.get_supplied_vmaf_models()

        if not os.path.isfile(self.model_path):
            # check if this is one of the supplied ones? e.g. user passed only a filename
            if self.model_path in supplied_models:
                self.model_path = os.path.join(FfmpegQualityMetrics.DEFAULT_VMAF_MODEL_DIRECTORY, self.model_path)
            else:
                raise FfmpegQualityMetricsError(
                    f"Could not find model at {self.model_path}. Please set --model-path to a valid VMAF .json model file."
                )

        try:
            if self.verbose:
                print_info(
                    f"Writing temporary VMAF information to: {self.temp_files['vmaf']}"
                )

            vmaf_opts = {
                "model_path": win_path_check(self.model_path),
                "phone_model": "1" if phone_model else "0",
                "log_path": win_path_check(self.temp_files["vmaf"]),
                "log_fmt": "json",
                "psnr": "1",
                "ssim": "1",
                "ms_ssim": "1",
                "n_threads": str(self.n_threads),
            }

            vmaf_opts_string = ":".join(f"{k}={v}" for k, v in vmaf_opts.items())

            filter_chains = [
                f"[1][0]scale2ref=flags={self.scaling_algorithm}[dist][ref]",
                "[dist]setpts=PTS-STARTPTS[dist1]",
                "[ref]setpts=PTS-STARTPTS[ref1]",
                f"[dist1][ref1]libvmaf='{vmaf_opts_string}'",
            ]

            self._run_ffmpeg_command(filter_chains)

            if not self.dry_run:
                with open(self.temp_files["vmaf"], "r") as in_vmaf:
                    vmaf_log = json.load(in_vmaf)
                    for frame_data in vmaf_log["frames"]:
                        # append frame number, increase +1
                        frame_data["metrics"]["n"] = int(frame_data["frameNum"]) + 1
                        self.vmaf_data.append(frame_data["metrics"])

        except Exception as e:
            raise e
        finally:
            if os.path.isfile(self.temp_files["vmaf"]):
                os.remove(self.temp_files["vmaf"])

        return self.vmaf_data

    def _run_ffmpeg_command(self, filter_chains=[]):
        """
        Run the ffmpeg command to get the quality metrics.
        The filter chains must be specified manually.
        """
        if not self.framerate:
            ref_framerate, dist_framerate = self._get_framerates()
        else:
            ref_framerate = self.framerate
            dist_framerate = self.framerate

        cmd = [
            "ffmpeg",
            "-nostdin",
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

        return run_command(cmd, self.dry_run, self.verbose)

    def calc_ssim_psnr(self):
        """Calculate SSIM and PSNR

        Raises:
            e: A generic error

        Returns:
            dict: SSIM and PSNR results, each with their own key
        """
        try:
            if self.verbose:
                print_info(
                    f"Writing temporary SSIM information to: {self.temp_files['ssim']}"
                )
                print_info(
                    f"Writing temporary PSNR information to: {self.temp_files['psnr']}"
                )

            filter_chains = [
                f"[1][0]scale2ref=flags={self.scaling_algorithm}[dist][ref]",
                "[dist]setpts=PTS-STARTPTS[distpts]",
                "[ref]setpts=PTS-STARTPTS[refpts]",
                "[distpts]split[dist1][dist2]",
                "[refpts]split[ref1][ref2]",
                f"[dist1][ref1]psnr='{win_path_check(self.temp_files['psnr'])}'",
                f"[dist2][ref2]ssim='{win_path_check(self.temp_files['ssim'])}'",
            ]

            self._run_ffmpeg_command(filter_chains)

            if not self.dry_run:
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
                        self.psnr_data.append(frame_data)

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
                        self.ssim_data.append(frame_data)

        except Exception as e:
            raise e
        finally:
            if os.path.isfile(self.temp_files["psnr"]):
                os.remove(self.temp_files["psnr"])
            if os.path.isfile(self.temp_files["ssim"]):
                os.remove(self.temp_files["ssim"])

        return {"ssim": self.ssim_data, "psnr": self.psnr_data}

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
        for key in ["ssim", "psnr", "vmaf"]:
            data = getattr(self, key + "_data")
            if len(data) == 0:
                continue

            value_key = key if key == "vmaf" else key + "_avg"
            values = [float(entry[value_key]) for entry in data]
            self.global_stats[key] = {
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

        if self.vmaf_data:
            all_dfs.append(pd.DataFrame(self.vmaf_data))

        if self.psnr_data and self.ssim_data:
            all_dfs.append(pd.DataFrame(self.psnr_data))
            all_dfs.append(pd.DataFrame(self.ssim_data))

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
        for key in ["ssim", "psnr", "vmaf"]:
            data = getattr(self, key + "_data")
            if len(data) == 0:
                continue
            ret[key] = data
        ret["global"] = self.get_global_stats()
        ret["input_file_dist"] = self.dist
        ret["input_file_ref"] = self.ref

        return json.dumps(ret, indent=4)
