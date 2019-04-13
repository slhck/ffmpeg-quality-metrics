FROM ubuntu:bionic
LABEL maintainer="Werner Robitza <werner.robitza@gmail.com>"
LABEL name="ffmpeg_quality_metrics"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl file g++ git locales make uuid-runtime python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -f UTF-8 en_US.UTF-8 \
    && useradd -m -s /bin/bash linuxbrew \
    && echo 'linuxbrew ALL=(ALL) NOPASSWD:ALL' >>/etc/sudoers

USER linuxbrew
WORKDIR /home/linuxbrew
ENV PATH=/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:$PATH \
    SHELL=/bin/bash

RUN git clone https://github.com/Linuxbrew/brew.git /home/linuxbrew/.linuxbrew/Homebrew \
    && mkdir /home/linuxbrew/.linuxbrew/bin \
    && ln -s ../Homebrew/bin/brew /home/linuxbrew/.linuxbrew/bin/ \
    && brew config

RUN brew tap varenc/ffmpeg \
    && brew install varenc/ffmpeg/ffmpeg --with-libvmaf

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY ffmpeg_quality_metrics.py .

CMD ["python3", "./ffmpeg_quality_metrics.py"]
