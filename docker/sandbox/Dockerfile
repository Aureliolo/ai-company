FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace && useradd -m -s /bin/bash sandbox

WORKDIR /workspace

USER sandbox

CMD ["bash"]
