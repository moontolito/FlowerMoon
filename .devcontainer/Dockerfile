FROM mcr.microsoft.com/devcontainers/base:1-ubuntu-24.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       python3 python3-tk python3-venv fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/flowermoon-venv \
    && chown -R vscode:vscode /opt/flowermoon-venv
ENV PATH="/opt/flowermoon-venv/bin:${PATH}"
COPY apps/transport/requirements.txt /tmp/flowermoon-requirements.txt
COPY web/portal/requirements.txt /tmp/portal-requirements.txt
RUN /opt/flowermoon-venv/bin/python -m pip install --no-cache-dir \
    -r /tmp/flowermoon-requirements.txt -r /tmp/portal-requirements.txt
