FROM python:3.9-slim
LABEL maintainer="Werner Robitza <werner.robitza@gmail.com>"
LABEL name="ffmpeg_quality_metrics"

RUN apt-get update -y && apt-get install -y \
  wget \
  xz-utils \
  python3-pandas \
  --no-install-recommends && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN wget -q https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz && \
  tar --strip-components 1 -C /usr/bin -xf ffmpeg-git-amd64-static.tar.xz --wildcards */ffmpeg && \
  rm ffmpeg-git-amd64-static.tar.xz

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY ffmpeg_quality_metrics ffmpeg_quality_metrics

CMD ["python3", "-m", "ffmpeg_quality_metrics"]
