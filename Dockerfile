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
# Point index.html at ?v=<hash> URLs so caches (Cloudflare, browsers) fetch the new bundle after each build
RUN npm run build \
 && v=$(cat dist/js/bundle.js dist/css/style.css | md5sum | cut -c1-8) \
 && sed -i "s#\./js/bundle\.js#./js/bundle.js?v=$v#; s#\./css/style\.css#./css/style.css?v=$v#" dist/index.html

# Debian's packaged matplotlib, because PyPI has no 32-bit ARM wheels for it (pip would try to compile)
FROM debian:trixie-slim AS plots
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-matplotlib \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -c "import matplotlib.pyplot"
WORKDIR /app
ENTRYPOINT ["python3", "analysis/plot_metrics.py"]

FROM nginx:1.28-alpine AS web
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
