# Travel Safety Watch video renderer
# Chromium (Playwright) draws the frames, ffmpeg encodes, Kokoro speaks (free, runs locally).
FROM mcr.microsoft.com/playwright:v1.63.0-noble

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/py \
 && /opt/py/bin/pip install --no-cache-dir kokoro-onnx soundfile numpy

# Voice model files (about 340 MB, downloaded once at build time)
ADD https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx /opt/kokoro/kokoro-v1.0.onnx
ADD https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin /opt/kokoro/voices-v1.0.bin

WORKDIR /app
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY . .

ENV PYTHON=/opt/py/bin/python \
    KOKORO_DIR=/opt/kokoro \
    PORT=8090 \
    OUT_DIR=/data/videos \
    WORK_DIR=/data/work \
    LAUNCH_DATE=2026-11-21
EXPOSE 8090
CMD ["node", "server.mjs"]
