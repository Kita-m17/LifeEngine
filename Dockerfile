# Targets:
#   web   - production bundle served by nginx (the default)
#   deps  - node + installed packages, used by the dev watcher in docker-compose.yml
#   plots - python + matplotlib for analysis/plot_metrics.py
#
# Every base image is published for arm64 and 32-bit ARM, so this builds on any Raspberry Pi
# (64-bit or 32-bit Raspberry Pi OS). node:24-alpine has no 32-bit ARM build, hence node 22.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build
COPY webpack.config.js ./
COPY src ./src
COPY dist ./dist
RUN npm run build

# Debian's packaged matplotlib, because PyPI has no 32-bit ARM wheels for it (pip would try to compile)
FROM debian:trixie-slim AS plots
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-matplotlib \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -c "import matplotlib.pyplot"
WORKDIR /app
ENTRYPOINT ["python3", "analysis/plot_metrics.py"]

FROM nginx:1.28-alpine AS web
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
