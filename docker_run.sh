#!/usr/bin/env bash
#
# Helper script to run Docker container

usage() {
    echo "Usage: $0 <dist> <ref> [OPTIONS]"
    echo
    echo "  <dist>    -- distorted video"
    echo "  <ref>     -- reference video"
    echo "  [OPTIONS] -- further options passed to ffmpeg_quality_metrics.py"
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

docker run \
    --rm \
    -v "$distDir":"/tmp/dist" \
    -v "$refDir":"/tmp/ref" \
    -t ffmpeg_quality_metrics \
    ./ffmpeg_quality_metrics.py \
    "/tmp/dist/$distFileBasename" \
    "/tmp/ref/$refFileBasename" \
    "$@"
