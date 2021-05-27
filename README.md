# FFmpeg Quality Metrics

[![PyPI version](https://img.shields.io/pypi/v/ffmpeg_quality_metrics.svg)](https://pypi.org/project/ffmpeg_quality_metrics)

Simple script for calculating quality metrics with FFmpeg.

Currently supports PSNR, SSIM, VMAF and VIF. It will output:

- the per-frame metrics
- metrics for each component (Y, U, V)
- global statistics (min/max/average/standard deviation)

Author: Werner Robitza <werner.robitza@gmail.com>

Contents:

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Running with Docker](#running-with-docker)
- [Output](#output)
- [API](#api)
- [License](#license)

------

## Requirements

- Python 3.6 or higher
- FFmpeg:
    - **Linux:** Download the git master build from [here](https://johnvansickle.com/ffmpeg/). Installation instructions, as well as how to add FFmpeg and FFprobe to your PATH, can be found [here](https://www.johnvansickle.com/ffmpeg/faq/).
    - **macOS:** Download the *snapshot* build from [here](https://evermeet.cx/ffmpeg/).
    - **Windows:** Download an FFmpeg binary from [here](https://www.gyan.dev/ffmpeg/builds/). The `git essentials` build will suffice. 

Put the `ffmpeg` executable in your `$PATH`.

*FFmpeg can be installed using Homebrew, but it is recommended that you use one of the FFmpeg builds linked above, otherwise libvmaf <v2.0.0 will be used, which is ~2x slower ([source](https://netflixtechblog.com/toward-a-better-quality-metric-for-the-video-community-7ed94e752a30)).*

## Installation

    pip3 install ffmpeg_quality_metrics

Or clone this repository, then run the tool with `python3 -m ffmpeg_quality_metrics`

## Usage

In the simplest case, if you have a distorted (encoded, maybe scaled) version and the reference:

```
ffmpeg_quality_metrics distorted.mp4 reference.avi
```

The distorted file will be automatically scaled to the resolution of the reference.

### Metrics

The following metrics are available:

| Metric | Description | Scale | Calculated by default? |
| ------ | ------ | ------ | ------ |
| PSNR | [Peak Signal to Noise Ratio](https://en.wikipedia.org/wiki/Peak_signal-to-noise_ratio) | dB | ✔️ |
| SSIM | [Structural Similarity](https://en.wikipedia.org/wiki/Structural_similarity) | 0-100 (higher is better) | ✔️ |
| VMAF | [Video Multi-Method Assessment Fusion](https://github.com/Netflix/vmaf) | 0-100 (higher is better) | No |
| VIF | Visual Information Fidelity | 0-100 (higher is better) | No |

### Extended Options

You can configure additional options related to scaling, speed etc.

See `ffmpeg_quality_metrics -h`:

```
usage: ffmpeg_quality_metrics [-h] [-n] [-k] [-v] [-p]
                   [-m {vmaf,psnr,ssim,vif} [{vmaf,psnr,ssim,vif} ...]]
                   [-s {fast_bilinear,bilinear,bicubic,experimental,neighbor,area,bicublin,gauss,sinc,lanczos,spline}]
                   [-r FRAMERATE] [-t THREADS] [-of {json,csv}]
                   [--model-path MODEL_PATH] [--phone-model]
                   [--n-threads N_THREADS]
                   dist ref

positional arguments:
  dist                  input file, distorted
  ref                   input file, reference

optional arguments:
  -h, --help            show this help message and exit

General options:
  -n, --dry-run         Do not run commands, just show what would be done
                        (default: False)
  -v, --verbose         Show verbose output (default: False)
  -p, --progress        Show a progress bar (default: False)
  -k, --keep-tmp        Keep temporary files for debugging purposes (default: False)

Metric options:
  -m {vmaf,psnr,ssim,vif} [{vmaf,psnr,ssim,vif} ...], 
  --metrics {vmaf,psnr,ssim,vif} [{vmaf,psnr,ssim,vif} ...]
        Metrics to calculate.
        Specify multiple metrics like '--metrics ssim vmaf' (default: ['psnr', 'ssim'])

FFmpeg options:
  -s {fast_bilinear,bilinear,bicubic,experimental,neighbor,area,bicublin,gauss,sinc,lanczos,spline}, --scaling-algorithm {fast_bilinear,bilinear,bicubic,experimental,neighbor,area,bicublin,gauss,sinc,lanczos,spline}
                        Scaling algorithm for ffmpeg (default: bicubic)
  -r FRAMERATE, --framerate FRAMERATE
                        Force an input framerate (default: None)
  -t THREADS, --threads THREADS
                        Number of threads to do the calculations (default: 0)

Output options:
  -of {json,csv}, --output-format {json,csv}
                        Output format for the metrics (default: json)

VMAF options:
  --model-path MODEL_PATH
                        Use a specific VMAF model file. If none is chosen,
                        picks a default model. You can also specify one of the
                        following built-in models: ['vmaf_v0.6.1.json',
                        'vmaf_4k_v0.6.1.json', 'vmaf_v0.6.1neg.json']
                        (default:
                        /Users/werner/Documents/Projects/slhck/ffmpeg-quality-
                        metrics/ffmpeg_quality_metrics/vmaf_models/vmaf_v0.6.1
                        .json)
  --phone-model         Enable VMAF phone model (default: False)
  --n-threads N_THREADS
                        Set the value of libvmaf's n_threads option. This
                        determines the number of threads that are used for
                        VMAF calculation (default: 8)

```

### Specifying VMAF Model

Use the `--model-path` option to set the path to a different VMAF model file.

This program supplies the following models:

```
vmaf_4k_v0.6.1.json
vmaf_v0.6.1.json
vmaf_v0.6.1neg.json
```

Use the `4k` version if you have a 4K reference sample. The `neg` version [is explained here](https://netflixtechblog.com/toward-a-better-quality-metric-for-the-video-community-7ed94e752a30).

You can either specify an absolute path to an existing model, e.g.:

```
/usr/local/opt/libvmaf/share/model/vmaf_v0.6.1neg.json
```

Or pass the file name to the built-in model. So both of these are equivalent:

```
ffmpeg_quality_metrics dist.mkv ref.mkv -m vmaf --model-path vmaf_v0.6.1neg.json
ffmpeg_quality_metrics dist.mkv ref.mkv -m vmaf --model-path /usr/local/opt/libvmaf/share/model/vmaf_v0.6.1neg.json
```

## Running with Docker

If you don't want to deal with dependencies, build the image with Docker:

```
docker build -t ffmpeg_quality_metrics .
```

This takes a few minutes and installs the latest `ffmpeg` [as a static build](https://johnvansickle.com/ffmpeg/) with libvmaf 2.x.

You can then run the container, which basically calls the Python script. To help you with mounting the volumes (since your videos are not stored in the container), you can run a helper script:

```
./docker_run.sh <dist> <ref> [OPTIONS]
```

Check the output of `./docker_run.sh` for more help.

For example, to run the tool with the bundled test videos and enable VMAF calculation:

```
./docker_run.sh test/dist-854x480.mkv test/ref-1280x720.mkv -ev
```

For Homebrew ffmpeg, a `Dockerfile-legacy` is provided.

## Output

This tool supports JSON or CSV output, including individual fields for Y, U, V, and global statistics, as well as frame numbers (`n`).

JSON example:

```
➜ ffmpeg_quality_metrics test/dist-854x480.mkv test/ref-1280x720.mkv -m ssim psnr vmaf
{
    "ssim": [
        {
            "n": 1,
            "ssim_y": 0.934,
            "ssim_u": 0.96,
            "ssim_v": 0.942,
            "ssim_avg": 0.945
        },
        {
            "n": 2,
            "ssim_y": 0.934,
            "ssim_u": 0.96,
            "ssim_v": 0.943,
            "ssim_avg": 0.946
        },
        {
            "n": 3,
            "ssim_y": 0.934,
            "ssim_u": 0.959,
            "ssim_v": 0.943,
            "ssim_avg": 0.945
        }
    ],
    "psnr": [
        {
            "n": 1,
            "mse_avg": 536.71,
            "mse_y": 900.22,
            "mse_u": 234.48,
            "mse_v": 475.43,
            "psnr_avg": 20.83,
            "psnr_y": 18.59,
            "psnr_u": 24.43,
            "psnr_v": 21.36
        },
        {
            "n": 2,
            "mse_avg": 535.29,
            "mse_y": 896.98,
            "mse_u": 239.4,
            "mse_v": 469.49,
            "psnr_avg": 20.84,
            "psnr_y": 18.6,
            "psnr_u": 24.34,
            "psnr_v": 21.41
        },
        {
            "n": 3,
            "mse_avg": 535.04,
            "mse_y": 894.89,
            "mse_u": 245.8,
            "mse_v": 464.43,
            "psnr_avg": 20.85,
            "psnr_y": 18.61,
            "psnr_u": 24.22,
            "psnr_v": 21.46
        }
    ],
    "vmaf": [
        {
            "psnr": 18.587308,
            "integer_motion2": 0.0,
            "integer_motion": 0.0,
            "integer_adm2": 0.69907,
            "integer_adm_scale0": 0.708183,
            "integer_adm_scale1": 0.733469,
            "integer_adm_scale2": 0.718624,
            "integer_adm_scale3": 0.67301,
            "ssim": 0.925976,
            "integer_vif_scale0": 0.539591,
            "integer_vif_scale1": 0.718022,
            "integer_vif_scale2": 0.751875,
            "integer_vif_scale3": 0.773503,
            "ms_ssim": 0.898265,
            "vmaf": 14.054853,
            "n": 1
        },
        {
            "psnr": 18.60299,
            "integer_motion2": 0.359752,
            "integer_motion": 0.368929,
            "integer_adm2": 0.698451,
            "integer_adm_scale0": 0.706706,
            "integer_adm_scale1": 0.73203,
            "integer_adm_scale2": 0.718262,
            "integer_adm_scale3": 0.672766,
            "ssim": 0.926521,
            "integer_vif_scale0": 0.540231,
            "integer_vif_scale1": 0.719566,
            "integer_vif_scale2": 0.753567,
            "integer_vif_scale3": 0.775864,
            "ms_ssim": 0.899353,
            "vmaf": 14.464182,
            "n": 2
        },
        {
            "psnr": 18.613101,
            "integer_motion2": 0.359752,
            "integer_motion": 0.359752,
            "integer_adm2": 0.697126,
            "integer_adm_scale0": 0.706542,
            "integer_adm_scale1": 0.731351,
            "integer_adm_scale2": 0.716454,
            "integer_adm_scale3": 0.671197,
            "ssim": 0.926481,
            "integer_vif_scale0": 0.539091,
            "integer_vif_scale1": 0.718657,
            "integer_vif_scale2": 0.753306,
            "integer_vif_scale3": 0.775984,
            "ms_ssim": 0.900086,
            "vmaf": 14.256442,
            "n": 3
        }
    ],
    "global": {
        "ssim": {
            "average": 0.945,
            "median": 0.945,
            "stdev": 0.0,
            "min": 0.945,
            "max": 0.946
        },
        "psnr": {
            "average": 20.84,
            "median": 20.84,
            "stdev": 0.008,
            "min": 20.83,
            "max": 20.85
        },
        "vmaf": {
            "average": 14.258,
            "median": 14.256,
            "stdev": 0.167,
            "min": 14.055,
            "max": 14.464
        }
    },
    "input_file_dist": "test/dist-854x480.mkv",
    "input_file_ref": "test/ref-1280x720.mkv"
}
```

CSV example:

```
➜ ffmpeg_quality_metrics test/dist-854x480.mkv test/ref-1280x720.mkv --enable-vmaf -of csv
n,adm2,motion2,ms_ssim,psnr,ssim,vif_scale0,vif_scale1,vif_scale2,vif_scale3,vmaf,mse_avg,mse_u,mse_v,mse_y,psnr_avg,psnr_u,psnr_v,psnr_y,ssim_avg,ssim_u,ssim_v,ssim_y,input_file_dist,input_file_ref
1,0.70704,0.0,0.89698,18.58731,0.92415,0.53962,0.71805,0.75205,0.77367,15.44212,536.71,234.48,475.43,900.22,20.83,24.43,21.36,18.59,0.945,0.96,0.942,0.934,test/dist-854x480.mkv,test/ref-1280x720.mkv
2,0.7064,0.35975,0.89806,18.60299,0.9247,0.54025,0.71961,0.75369,0.77607,15.85038,535.29,239.4,469.49,896.98,20.84,24.34,21.41,18.6,0.946,0.96,0.943,0.934,test/dist-854x480.mkv,test/ref-1280x720.mkv
3,0.70505,0.35975,0.89879,18.6131,0.92466,0.5391,0.71869,0.75344,0.77616,15.63546,535.04,245.8,464.43,894.89,20.85,24.22,21.46,18.61,0.945,0.959,0.943,0.934,test/dist-854x480.mkv,test/ref-1280x720.mkv
```

## API

The program exposes an API that you can use yourself:

```python
from ffmpeg_quality_metrics import FfmpegQualityMetrics as ffqm

ffqm("path/to/ref", "path/to/dist").calc(["ssim", "psnr"])
```

For more usage please read [the docs](https://htmlpreview.github.io/?https://github.com/slhck/ffmpeg-quality-metrics/blob/master/docs/ffmpeg_quality_metrics/ffmpeg_quality_metrics.html).

## License

ffmpeg_quality_metrics, Copyright (c) 2019-2021 Werner Robitza

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
