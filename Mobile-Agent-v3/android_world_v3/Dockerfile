# ============================================================
# Base image
# ============================================================
FROM openjdk:26-ea-21-jdk-slim

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# ============================================================
# System dependencies (Android emulator runtime)
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sudo wget unzip bzip2 \
    libdrm-dev libxkbcommon-dev libgbm-dev \
    libasound-dev libnss3 libxcursor1 libpulse-dev \
    libxshmfence-dev xauth xvfb x11vnc fluxbox wmctrl \
    libdbus-glib-1-2 ffmpeg \
    ca-certificates socat \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Android SDK configuration
# ============================================================
ARG ARCH=x86_64
ARG TARGET=google_apis
ARG API_LEVEL=33
ARG BUILD_TOOLS=33.0.0

ARG ANDROID_API_LEVEL=android-${API_LEVEL}
ARG ANDROID_APIS=${TARGET};${ARCH}
ARG EMULATOR_PACKAGE=system-images;${ANDROID_API_LEVEL};${ANDROID_APIS}
ARG PLATFORM_VERSION=platforms;${ANDROID_API_LEVEL}
ARG BUILD_TOOL=build-tools;${BUILD_TOOLS}
ARG ANDROID_CMD=commandlinetools-linux-11076708_latest.zip
ARG ANDROID_SDK_PACKAGES="${EMULATOR_PACKAGE} ${PLATFORM_VERSION} ${BUILD_TOOL} platform-tools emulator"

ENV ANDROID_SDK_ROOT=/opt/android
ENV PATH=$PATH:${ANDROID_SDK_ROOT}/cmdline-tools/tools/bin:${ANDROID_SDK_ROOT}/platform-tools:${ANDROID_SDK_ROOT}/emulator:${ANDROID_SDK_ROOT}/build-tools/${BUILD_TOOLS}
ENV DOCKER=true

# ============================================================
# Install Android command line tools
# ============================================================
RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/${ANDROID_CMD} -O /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d ${ANDROID_SDK_ROOT}/cmdline-tools && \
    mv ${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/tools && \
    rm -f /tmp/cmdline-tools.zip

# ============================================================
# Install Android SDK packages & emulator
# ============================================================
RUN yes | sdkmanager --licenses && \
    sdkmanager --verbose --no_https ${ANDROID_SDK_PACKAGES}

ARG EMULATOR_NAME=Pixel_6_API_33
ARG EMULATOR_DEVICE=pixel_6
ENV EMULATOR_NAME=${EMULATOR_NAME}
ENV DEVICE_NAME=${EMULATOR_DEVICE}

RUN echo "no" | avdmanager create avd \
    --force \
    --name "${EMULATOR_NAME}" \
    --device "${EMULATOR_DEVICE}" \
    --package "${EMULATOR_PACKAGE}"

# ============================================================
# Python 3.11 (from source)
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev libncurses5-dev libgdbm-dev \
    libssl-dev libreadline-dev libffi-dev \
    libsqlite3-dev libbz2-dev \
    && wget -q https://www.python.org/ftp/python/3.11.3/Python-3.11.3.tgz \
    && tar -xf Python-3.11.3.tgz \
    && cd Python-3.11.3 \
    && ./configure --enable-optimizations \
    && make -j$(nproc) \
    && make altinstall \
    && cd / \
    && rm -rf Python-3.11.3* \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/local/bin/python3.11 /usr/local/bin/python3 && \
    ln -sf /usr/local/bin/python3.11 /usr/local/bin/python

# ============================================================
# uv (Python package manager)
# ============================================================
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH=/root/.local/bin:$PATH

# ============================================================
# Application
# ============================================================
WORKDIR /app

# 先复制元数据（最大化缓存）
COPY pyproject.toml* setup.py* uv.lock* /app/

RUN uv pip install . --system --verbose || true

# 再复制完整源码
COPY . /app

RUN chmod +x docker_setup/*.sh

# 最终安装（源码变更才会触发）
RUN uv pip install . --system --verbose
RUN uv pip install -r requirements.txt --system --verbose

# ============================================================
# Expose ports (5000 for app server, 5556 for adb forwarding)
# ============================================================
EXPOSE 5000 5556

# ============================================================
# Entry point
# ============================================================
ENTRYPOINT ["./docker_setup/entrypoint.sh"]
