#!/usr/bin/env bash
#
# Helper script to run Docker container

py_usage() {
    docker run \
    -t ffmpeg-quality-metrics:latest \
    python3 -m ffmpeg_quality_metrics -h
}

usage() {
    echo "Usage: $0 <dist> <ref> [OPTIONS]"
    echo
    echo "  <dist>    -- distorted video"
    echo "  <ref>     -- reference video"
    echo "  [OPTIONS] -- further options passed to ffmpeg_quality_metrics.py, see below"
    echo
    py_usage
    exit 1
}

if [ $# -lt 2 ]; then
    usage
fi

distFile="$1"
refFile="$2"

distFileBasename="$(basename $1)"
refFileBasename="$(basename $2)"

distDir="$(realpath "$(dirname "$1")")"
refDir="$(realpath "$(dirname "$2")")"

shift; shift

if ! docker image inspect ffmpeg-quality-metrics:latest > /dev/null 2>&1; then
    echo "Image 'ffmpeg-quality-metrics:latest' not found, building it first ..."
    docker build -t ffmpeg-quality-metrics:latest .
fi

docker run \
    --rm \
    -v "$distDir":"/tmp/dist" \
    -v "$refDir":"/tmp/ref" \
    -t ffmpeg-quality-metrics:latest \
    python3 -m ffmpeg_quality_metrics \
    "/tmp/dist/$distFileBasename" \
    "/tmp/ref/$refFileBasename" \
    "$@"
