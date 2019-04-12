# ffmpeg_quality_metrics

Simple script for calculating quality metrics with FFmpeg.

Currently supports PSNR and SSIM. VMAF to follow.

Author: Werner Robitza <werner.robitza@gmail.com>

Contents:

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Running with Docker](#running-with-docker)
- [Output](#output)
- [License](#license)

------

## Requirements

- Python 3.6
- FFmpeg:
    - download a static build from [their website](http://ffmpeg.org/download.html))
    - put the `ffmpeg` executable in your `$PATH`
- `pip3 install -r requirements.txt`

Optionally, you may install FFmpeg with `libvmaf` support to run VMAF score calculation.

## Installation

Clone this repo and run `ffmpeg_quality_metrics.py`.

## Usage

See `ffmpeg_quality_metrics.py -h`.

## Running with Docker

If you don't want to deal with dependencies, build the image with Docker:

```
docker build -t ffmpeg_quality_metrics .
```

This installs `ffmpeg` with all dependencies. You can then run the container, which basically calls the Python script. To help you with mounting the volumes (since your videos are not stored in the container), you can run a helper script:

```
./docker_run.sh
```

## Output

JSON or CSV, including individual fields for Y, U, V, and averages, as well as frame numbers.

JSON example:

```
➜ ./ffmpeg_quality_metrics.py test/dist-854x480.mkv test/ref-1280x720.mkv -o json
{
    "ssim": [
        {
            "n": 1,
            "ssim_y": 0.936,
            "ssim_u": 0.961,
            "ssim_v": 0.946,
            "ssim_avg": 0.947
        },
        {
            "n": 2,
            "ssim_y": 0.936,
            "ssim_u": 0.961,
            "ssim_v": 0.946,
            "ssim_avg": 0.948
        },
        {
            "n": 3,
            "ssim_y": 0.936,
            "ssim_u": 0.96,
            "ssim_v": 0.947,
            "ssim_avg": 0.947
        }
    ],
    "psnr": [
        {
            "n": 1,
            "mse_avg": 529.56,
            "mse_y": 887.35,
            "mse_u": 233.89,
            "mse_v": 467.43,
            "psnr_avg": 20.89,
            "psnr_y": 18.65,
            "psnr_u": 24.44,
            "psnr_v": 21.43
        },
        {
            "n": 2,
            "mse_avg": 528.16,
            "mse_y": 884.16,
            "mse_u": 238.83,
            "mse_v": 461.49,
            "psnr_avg": 20.9,
            "psnr_y": 18.67,
            "psnr_u": 24.35,
            "psnr_v": 21.49
        },
        {
            "n": 3,
            "mse_avg": 527.87,
            "mse_y": 882.13,
            "mse_u": 245.13,
            "mse_v": 456.35,
            "psnr_avg": 20.91,
            "psnr_y": 18.68,
            "psnr_u": 24.24,
            "psnr_v": 21.54
        }
    ]
}
```

CSV example:

```
➜ ./ffmpeg_quality_metrics.py test/dist-854x480.mkv test/ref-1280x720.mkv -o csv
n,mse_avg,mse_u,mse_v,mse_y,psnr_avg,psnr_u,psnr_v,psnr_y,ssim_avg,ssim_u,ssim_v,ssim_y
1,529.56,233.89,467.43,887.35,20.89,24.44,21.43,18.65,0.947,0.961,0.946,0.936
2,528.16,238.83,461.49,884.16,20.9,24.35,21.49,18.67,0.948,0.961,0.946,0.936
3,527.87,245.13,456.35,882.13,20.91,24.24,21.54,18.68,0.947,0.96,0.947,0.936
```

## License

ffmpeg_quality_metrics, Copyright (c) 2019 Werner Robitza

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.