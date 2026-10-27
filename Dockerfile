# creek in a container: build the web player, then run the station.
#
#   docker build -t creek .
#   docker run -d --name creek --restart unless-stopped -p 7889:7889 -v creek-data:/data \
#     -e CREEK_KEY=choose-a-long-key creek
#
# Music, the library database and links.txt live in the /data volume (CREEK_HOME).

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
# yt-dlp solves YouTube's JavaScript challenges with Node (Debian's own is too old)
COPY --from=web /usr/local/bin/node /usr/local/bin/node
RUN pip install --no-cache-dir uv==0.5.11
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY creek/ creek/
COPY --from=web /web/dist web/dist
ENV CREEK_HOME=/data PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 7889
CMD ["python", "-m", "creek"]
