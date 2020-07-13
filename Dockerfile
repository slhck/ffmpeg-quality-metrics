FROM homebrew/brew:2.4.5
LABEL maintainer="Werner Robitza <werner.robitza@gmail.com>"
LABEL name="ffmpeg_quality_metrics"

RUN brew tap homebrew-ffmpeg/ffmpeg \
    && brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libvmaf

COPY requirements.txt .
COPY ffmpeg_quality_metrics ffmpeg_quality_metrics
RUN pip3 install -r requirements.txt

CMD ["python3", "-m", "ffmpeg_quality_metrics"]
