# FFmpeg Quality Metrics

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-5-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

[![PyPI version](https://img.shields.io/pypi/v/ffmpeg-quality-metrics.svg)](https://pypi.org/project/ffmpeg-quality-metrics)

[![Python package](https://github.com/slhck/ffmpeg-quality-metrics/actions/workflows/python-package.yml/badge.svg)](https://github.com/slhck/ffmpeg-quality-metrics/actions/workflows/python-package.yml)

Calculate various video quality metrics with FFmpeg.

Currently supports PSNR, SSIM, VMAF and VIF. It will output:

- the per-frame metrics
- metrics for each plane (Y, U, V) or components/submetrics (in the case of VIF, VMAF)
- global statistics (min/max/average/standard deviation)

Author: Werner Robitza <werner.robitza@gmail.com>

**Note:** Previous versions installed a `ffmpeg_quality_metrics` executable. To harmonize it with other tools, now the executable is called `ffmpeg-quality-metrics`. Please ensure you remove the old executable (e.g. run `which ffmpeg_quality_metrics` and remove the file).

**Contents:**

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Metrics](#metrics)
  - [Extended Options](#extended-options)
  - [VMAF-specific Settings](#vmaf-specific-settings)
- [Examples](#examples)
- [Running with Docker](#running-with-docker)
- [Output](#output)
  - [JSON Output](#json-output)
  - [CSV Output](#csv-output)
- [API](#api)
- [Contributors](#contributors)
- [License](#license)

------

## Requirements

What you need:

- OS: Linux, macOS, Windows
- Python 3.9 or higher
- FFmpeg 7.1 or higher is recommended:
    - **Linux:** Download the git master build from [here](https://johnvansickle.com/ffmpeg/). Installation instructions, as well as how to add FFmpeg and FFprobe to your PATH, can be found [here](https://www.johnvansickle.com/ffmpeg/faq/).
    - **macOS:** Download the *snapshot* build from [here](https://evermeet.cx/ffmpeg/) or install via `brew install ffmpeg`.
    - **Windows:** Download an FFmpeg binary from [here](https://www.gyan.dev/ffmpeg/builds/). The `git essentials` build will suffice.

Put the `ffmpeg` executable in your `$PATH`.

If you want to calculate VMAF, your ffmpeg build should include `libvmaf 2.3.1` or higher. This is the case with the static builds listed above or the Homebrew `ffmpeg` v5.1 and above.

## Installation

Using pip:

```bash
pip3 install ffmpeg-quality-metrics
```

Or clone this repository, then run the tool with `python3 -m ffmpeg_quality_metrics`.

## Usage

In the simplest case, if you have a distorted (encoded, maybe scaled) version and the reference:

```bash
ffmpeg-quality-metrics distorted.mp4 reference.y4m
```

The distorted file will be automatically scaled to the resolution of the reference, and the default metrics (PSNR, SSIM) will be computed.

Note that if your distorted file is not in time sync with the reference, you can use the `--dist-delay` option to delay the distorted file by a certain amount of seconds (positive or negative).

> [!NOTE]
> Raw YUV files cannot be read with this tool. We should all be using lossless containers like Y4M or FFV1. If you have a raw YUV file, you can use FFmpeg to convert it to a format that this tool can read. Adjust the options as needed.
>
> ```bash
> ffmpeg -framerate 24 -video_size 1920x1080 -pix_fmt yuv420p -i input.yuv output.y4m
> ```

### Metrics

The following metrics are available in this tool:

| Metric | Description                                                                            | Scale                    | Components/Submetrics                                                                                                                                                                                                                       | Calculated by default? |
| ------ | -------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| PSNR   | [Peak Signal to Noise Ratio](https://en.wikipedia.org/wiki/Peak_signal-to-noise_ratio) | dB                       | `mse_avg`<br> `mse_y`<br> `mse_u`<br> `mse_v`<br> `psnr_avg`<br> `psnr_y`<br> `psnr_u`<br> `psnr_v`                                                                                                                                                              | ✔️                      |
| SSIM   | [Structural Similarity](https://en.wikipedia.org/wiki/Structural_similarity)           | 0-100 (higher is better) | `ssim_y`<br> `ssim_u`<br> `ssim_v`<br> `ssim_avg`                                                                                                                                                                                                    | ✔️                      |
| VMAF   | [Video Multi-Method Assessment Fusion](https://github.com/Netflix/vmaf)                | 0-100 (higher is better) | `vmaf`<br> `integer_adm2`<br> `integer_adm_scale0`<br> `integer_adm_scale1`<br> `integer_adm_scale2`<br> `integer_adm_scale3`<br> `integer_motion2`<br> `integer_motion`<br> `integer_vif_scale0`<br> `integer_vif_scale1`<br> `integer_vif_scale2`<br> `integer_vif_scale3` | No                     |
| VIF    | Visual Information Fidelity                                                            | 0-100 (higher is better) | `scale_0`<br> `scale_1`<br> `scale_2`<br> `scale_3`                                                                                                                                                                                                  | No                     |

As shown in the table, every metric can have more than one submetric computed, and they will be printed in the output.

If you want to calculate additional metrics, enable them with the `--metrics` option:

```
ffmpeg-quality-metrics distorted.mp4 reference.avi --metrics psnr ssim vmaf
```

Specify multiple metrics by separating them with a space (e.g., in the above example, `psnr ssim vmaf`).

Here, VMAF uses the default model. You can specify a different model with the [`--vmaf-model` option](#specifying-vmaf-model). VMAF also allows you to calculate even [more additional features](https://github.com/Netflix/vmaf/blob/master/resource/doc/features.md) as submetrics. You can enable these with the [`--vmaf-features` option](#specifying-vmaf-model-params).

### Extended Options

You can configure additional options related to scaling, speed etc.

See `ffmpeg-quality-metrics -h`:

```
usage: ffmpeg-quality-metrics [-h] [-n] [-v] [-p] [-k] [--tmp-dir TMP_DIR]
                              [-m {vmaf,psnr,ssim,vif} [{vmaf,psnr,ssim,vif} ...]]
                              [-s {fast_bilinear,bilinear,bicubic,experimental,neighbor,area,bicublin,gauss,sinc,lanczos,spline}]
                              [-r FRAMERATE] [--dist-delay DIST_DELAY] [-t THREADS] [-of {json,csv}]
                              [--vmaf-model-path VMAF_MODEL_PATH]
                              [--vmaf-model-params VMAF_MODEL_PARAMS [VMAF_MODEL_PARAMS ...]]
                              [--vmaf-threads VMAF_THREADS] [--vmaf-subsample VMAF_SUBSAMPLE]
                              [--vmaf-features VMAF_FEATURES [VMAF_FEATURES ...]]
                              dist ref

ffmpeg-quality-metrics v3.2.1

positional arguments:
  dist                                  input file, distorted
  ref                                   input file, reference

options:
  -h, --help                            show this help message and exit

General options:
  -n, --dry-run                         Do not run commands, just show what would be done (default:
                                        False)
  -v, --verbose                         Show verbose output (default: False)
  -p, --progress                        Show a progress bar (default: False)
  -k, --keep-tmp                        Keep temporary files for debugging purposes (default: False)
  --tmp-dir TMP_DIR                     Directory to store temporary files in (will use system
                                        default if not specified) (default: None)

Metric options:
  -m {vmaf,psnr,ssim,vif} [{vmaf,psnr,ssim,vif} ...], --metrics {vmaf,psnr,ssim,vif} [{vmaf,psnr,ssim,vif} ...]
                                        Metrics to calculate. Specify multiple metrics like '--
                                        metrics ssim vmaf' (default: ['psnr', 'ssim'])

FFmpeg options:
  -s {fast_bilinear,bilinear,bicubic,experimental,neighbor,area,bicublin,gauss,sinc,lanczos,spline}, --scaling-algorithm {fast_bilinear,bilinear,bicubic,experimental,neighbor,area,bicublin,gauss,sinc,lanczos,spline}
                                        Scaling algorithm for ffmpeg (default: bicubic)
  -r FRAMERATE, --framerate FRAMERATE   Force an input framerate (default: None)
  --dist-delay DIST_DELAY               Delay the distorted video against the reference by this many
                                        seconds (default: 0.0)
  -t THREADS, --threads THREADS         Number of threads to do the calculations (default: 0)

Output options:
  -of {json,csv}, --output-format {json,csv}
                                        Output format for the metrics (default: json)

VMAF options:
  --vmaf-model-path VMAF_MODEL_PATH     Use a specific VMAF model file. If none is chosen, picks a
                                        default model. You can also specify one of the following
                                        built-in models: ['vmaf_v0.6.1.json', 'vmaf_4k_v0.6.1.json',
                                        'vmaf_v0.6.1neg.json'] (default: /opt/homebrew/opt/libvmaf/s
                                        hare/libvmaf/model/vmaf_v0.6.1.json)
  --vmaf-model-params VMAF_MODEL_PARAMS [VMAF_MODEL_PARAMS ...]
                                        A list of params to pass to the VMAF model, specified as
                                        key=value. Specify multiple params like '--vmaf-model-params
                                        enable_transform=true enable_conf_interval=true' (default:
                                        None)
  --vmaf-threads VMAF_THREADS           Set the value of libvmaf's n_threads option. This determines
                                        the number of threads that are used for VMAF calculation.
                                        Set to 0 for auto. (default: 0)
  --vmaf-subsample VMAF_SUBSAMPLE       Set the value of libvmaf's n_subsample option. This is the
                                        subsampling interval, so set to 1 for default behavior.
                                        (default: 1)
  --vmaf-features VMAF_FEATURES [VMAF_FEATURES ...]
                                        A list of feature to enable. Pass the names of the features
                                        and any optional params. See https://github.com/Netflix/vmaf
                                        /blob/master/resource/doc/features.md for a list of
                                        available features. Params must be specified as 'key=value'.
                                        Multiple params must be separated by ':'. Specify multiple
                                        features like '--vmaf-features cambi:full_ref=true ciede'
                                        (default: None)
```

### VMAF-specific Settings

As VMAF is more complex than the other metrics, it has a few more options.

#### Specifying VMAF Model

Use the `--vmaf-model-path` option to set the path to a different VMAF model file. The default is `vmaf_v0.6.1.json`.

`libvmaf` version 2.x supports JSON-based model files only. This program has built-in support for the following models:

```
vmaf_v0.6.1.json
vmaf_4k_v0.6.1.json
vmaf_v0.6.1neg.json
```

Use the `4k` version if you have a 4K reference sample. The `neg` version [is explained here](https://netflixtechblog.com/toward-a-better-quality-metric-for-the-video-community-7ed94e752a30).

You can either specify an absolute path to an existing model, e.g.:

```
/usr/local/opt/libvmaf/share/model/vmaf_v0.6.1neg.json
```

Or pass the file name to the built-in model. So all of these work:

```bash
# use a downloaded JSON model for libvmaf 2.x
ffmpeg-quality-metrics dist.mkv ref.mkv -m vmaf --vmaf-model-path vmaf_v0.6.1neg.json

# use a different path for models on your system
ffmpeg-quality-metrics dist.mkv ref.mkv -m vmaf --vmaf-model-path /usr/local/opt/libvmaf/share/model/vmaf_v0.6.1neg.json
```

#### Specifying VMAF Features

VMAF includes several metrics, each of which correspond to a feature name. By default, only three core features are used. Use the `--vmaf-features` option to enable additional features on top of the core features.

The following table shows the available features:

| Metric    | Feature name    | Core feature in VMAF? |
| --------- | --------------- | --------------------- |
| PSNR      | `psnr`          |                       |
| PSNR-HVS  | `psnr_hvs`      |                       |
| CIEDE2000 | `ciede`         |                       |
| CAMBI     | `cambi`         |                       |
| VIF       | `vif`           | ✔️                     |
| ADM       | `adm`           | ✔️                     |
| Motion    | `motion`        | ✔️                     |
| SSIM      | `float_ssim`    |                       |
| MS-SSIM   | `float_ms_ssim` |                       |

To find out more about the features, check out the [VMAF documentation](https://github.com/Netflix/vmaf/blob/master/resource/doc/features.md).

For example, to enable the CAMBI feature, use:

```bash
ffmpeg-quality-metrics dist.mkv ref.mkv -m vmaf --vmaf-features cambi
```

#### VMAF Feature Parameters

Some features additionally take a number of optional parameters. The following table shows the available parameters for each feature:

| Feature   | Parameter                | Default  | Description                                                                                                                        |
| --------- | ------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `adm`     | `adm_csf_mode`           | `0`      | Contrast sensitivity function                                                                                                      |
| `adm`     | `adm_enhn_gain_limit`    | `100.0`  | Enhancement gain imposed on adm, must be >= 1.0, where 1.0 means the gain is completely disabled                                   |
| `adm`     | `adm_norm_view_dist`     | `3.0`    | Normalized viewing distance = viewing distance / ref display's physical height                                                     |
| `adm`     | `adm_ref_display_height` | `1080`   | Reference display height in pixels                                                                                                 |
| `adm`     | `debug`                  | `false`  | Debug mode: enable additional output                                                                                               |
| `cambi`   | `enc_bitdepth`           |          | Encoding bitdepth.                                                                                                                 |
| `cambi`   | `enc_height`             |          | Encoding height.                                                                                                                   |
| `cambi`   | `enc_width`              |          | Encoding width.                                                                                                                    |
| `cambi`   | `eotf`                   | `bt1886` | Determines the EOTF used to compute the visibility thresholds.                                                                     |
| `cambi`   | `full_ref`               | `false`  | Set to `true` to enable full-reference CAMBI calculation.                                                                          |
| `cambi`   | `heatmaps_path`          |          | Set to a target folder where the CAMBI heatmaps will be stored as `.gray` files                                                    |
| `cambi`   | `max_log_contrast`       | `2`      | Maximum contrast in log luma level (2^max_log_contrast) at 10-bits.                                                                |
| `cambi`   | `src_height`             |          | Source height. Only used when full_ref=true.                                                                                       |
| `cambi`   | `src_width`              |          | Source width. Only used when full_ref=true.                                                                                        |
| `cambi`   | `topk`                   | `0.2`    | Ratio of pixels for the spatial pooling computation.                                                                               |
| `cambi`   | `tvi_threshold`          | `0.75`   | Visibility threshold for luminance ΔL < tvi_threshold*L_mean.                                                                      |
| `cambi`   | `window_size`            | `63`     | Window size to compute CAMBI: 63 corresponds to ~1 degree at 4k.                                                                   |
| `motion`  | `debug`                  | `true`   | Enable additional output for debugging.                                                                                            |
| `motion`  | `motion_force_zero`      | `false`  | Force the motion score to be zero. This parameter is a feature-specific parameter.                                                 |
| `ms_ssim` | `clip_db`                | `false`  | Clip dB scores                                                                                                                     |
| `ms_ssim` | `enable_db`              | `false`  | Write MS-SSIM values as dB                                                                                                         |
| `ms_ssim` | `enable_lcs`             | `false`  | Enable luminance, contrast and structure intermediate output                                                                       |
| `ssim`    | `clip_db`                | `false`  | Clip dB scores                                                                                                                     |
| `ssim`    | `enable_db`              | `false`  | Write SSIM values as dB                                                                                                            |
| `ssim`    | `enable_lcs`             | `false`  | Enable luminance, contrast and structure intermediate output                                                                       |
| `vif`     | `debug`                  | `false`  | Debug mode: enable additional output                                                                                               |
| `vif`     | `vif_enhn_gain_limit`    | `100.0`  | Enhancement gain imposed on vif, must be >= 1.0, where 1.0 means the gain is completely disabled                                   |
| `vif`     | `vif_kernelscale`        | `1.0`    | Scaling factor for the gaussian kernel (2.0 means multiplying the standard deviation by 2 and enlarge the kernel size accordingly) |

The parameters are specified as `key=value` pairs, separated by `:`. For example, to enable the full-reference CAMBI calculation, use:

```bash
ffmpeg-quality-metrics dist.mkv ref.mkv -m vmaf --vmaf-features cambi:full_ref=true
```

To generate the CAMBI heatmaps, use:

```bash
ffmpeg-quality-metrics dist.mkv ref.mkv -m vmaf --vmaf-features cambi:heatmaps_path=/tmp/cambi
```

## Examples

Run PSNR, SSIM, VMAF and VIF at the same time:

```bash
ffmpeg-quality-metrics dist.mkv ref.mkv \
    -m psnr ssim vmaf vif
```

Run VMAF with all the features:

```bash
ffmpeg-quality-metrics dist.mkv ref.mkv \
    -m vmaf \
    --vmaf-features ciede cambi psnr psnr_hvs motion adm vif
```

Enable feature options for CAMBI full-reference calculation:

```bash
ffmpeg-quality-metrics dist.mkv ref.mkv \
    -m vmaf \
    --vmaf-features cambi:full_ref=true
```

## Running with Docker

If you don't want to deal with dependencies, build the image with Docker:

```
docker build -t ffmpeg-quality-metrics .
```

This takes a few minutes and installs the latest `ffmpeg` [as a static build](https://johnvansickle.com/ffmpeg/).

You can then run the container, which basically calls the Python script. To help you with mounting the volumes (since your videos are not stored in the container), you can run a helper script:

```bash
./docker_run.sh <dist> <ref> [OPTIONS]
```

Check the output of `./docker_run.sh` for more help.

For example, to run the tool with the bundled test videos and enable VMAF calculation:

```bash
./docker_run.sh test/dist-854x480.mkv test/ref-1280x720.mkv -m vmaf
```

## Output

This tool supports JSON or CSV output, including individual fields for planes/components/submetrics, and global statistics, as well as frame numbers (`n`).

### JSON Output

The JSON output will include a key for each metric, and the value will be a list of values for each frame. Each frame is a dictionary with individual metrics per frame.

For instance, PSNR and SSIM output averages as well as per-component metrics. VMAF outputs different metrics depending on the enabled features.

The `global` key contains global statistics for each metric and its submetrics.

See the [`example.json`](test/example.json) file for an example of the output.

### CSV Output

CSV output is using the [tidy data](https://cran.r-project.org/web/packages/tidyr/vignettes/tidy-data.html) principle, using one column per feature and one line per frame (observation).

Example:

```csv
n,adm2,motion2,ms_ssim,psnr,ssim,vif_scale0,vif_scale1,vif_scale2,vif_scale3,vmaf,mse_avg,mse_u,mse_v,mse_y,psnr_avg,psnr_u,psnr_v,psnr_y,ssim_avg,ssim_u,ssim_v,ssim_y,input_file_dist,input_file_ref
1,0.70704,0.0,0.89698,18.58731,0.92415,0.53962,0.71805,0.75205,0.77367,15.44212,536.71,234.48,475.43,900.22,20.83,24.43,21.36,18.59,0.945,0.96,0.942,0.934,test/dist-854x480.mkv,test/ref-1280x720.mkv
2,0.7064,0.35975,0.89806,18.60299,0.9247,0.54025,0.71961,0.75369,0.77607,15.85038,535.29,239.4,469.49,896.98,20.84,24.34,21.41,18.6,0.946,0.96,0.943,0.934,test/dist-854x480.mkv,test/ref-1280x720.mkv
3,0.70505,0.35975,0.89879,18.6131,0.92466,0.5391,0.71869,0.75344,0.77616,15.63546,535.04,245.8,464.43,894.89,20.85,24.22,21.46,18.61,0.945,0.959,0.943,0.934,test/dist-854x480.mkv,test/ref-1280x720.mkv
```

As there is no tidy way to represent global data in the same CSV file, you can use other tools to aggregate the data.

## API

The program exposes an API that you can use yourself:

```python
from ffmpeg_quality_metrics import FfmpegQualityMetrics

ffqm = FfmpegQualityMetrics("path/to/reference-video.mp4", "path/to/distorted-video.mp4")

metrics = ffqm.calculate(["ssim", "psnr"])

# check the available metrics
print(metrics.keys())
# ['ssim', 'psnr']

# get the SSIM values for the first frame
print(metrics["ssim"][0])
# {'n': 1, 'ssim_y': 0.934, 'ssim_u': 0.96, 'ssim_v': 0.942, 'ssim_avg': 0.945}

# average the ssim_y values over all frames
print(sum([frame["ssim_y"] for frame in metrics["ssim"]]) / len(metrics["ssim"]))

# or just get the global stats
print(ffqm.get_global_stats()["ssim"]["ssim_y"]["average"])
```

For more usage please read [the docs](https://htmlpreview.github.io/?https://github.com/slhck/ffmpeg-quality-metrics/blob/master/docs/ffmpeg_quality_metrics.html).

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/OrkunKocyigit"><img src="https://avatars.githubusercontent.com/u/10797423?v=4?s=100" width="100px;" alt="Orkun Koçyiğit"/><br /><sub><b>Orkun Koçyiğit</b></sub></a><br /><a href="https://github.com/slhck/ffmpeg-quality-metrics/commits?author=OrkunKocyigit" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/CrypticSignal"><img src="https://avatars.githubusercontent.com/u/48166845?v=4?s=100" width="100px;" alt="Hamas Shafiq"/><br /><sub><b>Hamas Shafiq</b></sub></a><br /><a href="https://github.com/slhck/ffmpeg-quality-metrics/commits?author=CrypticSignal" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://codecalamity.com/"><img src="https://avatars.githubusercontent.com/u/3275435?v=4?s=100" width="100px;" alt="Chris Griffith"/><br /><sub><b>Chris Griffith</b></sub></a><br /><a href="https://github.com/slhck/ffmpeg-quality-metrics/commits?author=cdgriffith" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://codecalamity.com/"><img src="https://avatars.githubusercontent.com/u/17472224?v=4?s=100" width="100px;" alt="Ignacio Peletier"/><br /><sub><b>Ignacio Peletier</b></sub></a><br /><a href="https://github.com/slhck/ffmpeg-quality-metrics/commits?author=Sorkanius" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/nav9"><img src="https://avatars.githubusercontent.com/u/2093933?v=4?s=100" width="100px;" alt="Nav"/><br /><sub><b>Nav</b></sub></a><br /><a href="https://github.com/slhck/ffmpeg-quality-metrics/issues?q=author%3Anav9" title="Bug reports">🐛</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License

ffmpeg-quality-metrics, Copyright (c) 2019-2024 Werner Robitza

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

For VMAF models, see `ffmpeg_quality_metrics/vmaf_models/LICENSE`.
