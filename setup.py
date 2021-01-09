# Always prefer setuptools over distutils
from setuptools import setup
# To use a consistent encoding
from codecs import open
import os

here = os.path.abspath(os.path.dirname(__file__))

# Versioning
with open(os.path.join(here, 'ffmpeg_quality_metrics', '__init__.py')) as version_file:
    version = eval(version_file.read().split("\n")[0].split("=")[1].strip())

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

try:
    import pypandoc
    long_description = pypandoc.convert_text(long_description, 'rst', format='md')
except ImportError:
    print("pypandoc module not found, could not convert Markdown to RST")

setup(
    name='ffmpeg_quality_metrics',
    version=version,
    description='Calculate quality metrics with FFmpeg (SSIM, PSNR, VMAF)',
    long_description=long_description,
    url='https://github.com/slhck/ffmpeg-quality-metrics',
    author='Werner Robitza',
    author_email='werner.robitza@gmail.com',
    license='MIT',
    install_requires=['pandas'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Multimedia :: Video',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    packages=['ffmpeg_quality_metrics'],
    entry_points={
        'console_scripts': [
            'ffmpeg_quality_metrics=ffmpeg_quality_metrics.__main__:main',
        ],
    },
)
