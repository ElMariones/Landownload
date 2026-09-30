# Stage 1: build the web UI.
FROM node:22-slim AS ui
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY public public
COPY src src
RUN npm run build

# Stage 2: the server, with FFmpeg for merging and Node for yt-dlp's JavaScript challenges.
FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ui /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY yt_dlp_plugins yt_dlp_plugins
COPY --from=ui /app/dist dist

ENV LANDOWNLOAD_HOST=0.0.0.0 \
    LANDOWNLOAD_PORT=8000 \
    LANDOWNLOAD_DATA=/data \
    LANDOWNLOAD_OPEN=1 \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
CMD ["python", "-m", "backend"]
