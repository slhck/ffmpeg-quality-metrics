# Always prefer setuptools over distutils
from setuptools import setup

import os

here = os.path.abspath(os.path.dirname(__file__))

# Versioning
with open(os.path.join(here, "ffmpeg_quality_metrics", "__init__.py")) as version_file:
    # parse the string that looks like '__version__ = "3.1.2"'
    for line in version_file:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"')
            break

# Get the long description from the README file
with open(os.path.join(here, "README.md")) as f:
    long_description = f.read()

setup(
    name="ffmpeg_quality_metrics",
    version=version,
    description="Calculate video quality metrics with FFmpeg (SSIM, PSNR, VMAF)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/slhck/ffmpeg-quality-metrics",
    author="Werner Robitza",
    author_email="werner.robitza@gmail.com",
    license="MIT",
    install_requires=["pandas", "tqdm", "ffmpeg-progress-yield>=0.3.0"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    packages=["ffmpeg_quality_metrics"],
    include_package_data=True,
    package_data={"ffmpeg_quality_metrics": ["vmaf_models/*.json", "py.typed"]},
    entry_points={
        "console_scripts": [
            "ffmpeg_quality_metrics=ffmpeg_quality_metrics.__main__:main",
            "ffmpeg-quality-metrics=ffmpeg_quality_metrics.__main__:main",
        ],
    },
)
