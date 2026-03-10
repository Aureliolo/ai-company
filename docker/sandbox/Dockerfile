FROM node:22-slim AS node-base

FROM python:3.14-slim

COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox

WORKDIR /workspace

USER sandbox

CMD ["bash"]
