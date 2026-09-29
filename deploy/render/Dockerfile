FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 DISPLAY=:1
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-tk python3-venv ca-certificates fonts-dejavu-core \
    xvfb x11-utils x11vnc openbox novnc websockify supervisor tini \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/flowermoon-venv
ENV PATH="/opt/flowermoon-venv/bin:${PATH}"
WORKDIR /opt/flowermoon
COPY apps/transport/requirements.txt /tmp/transport-requirements.txt
COPY web/portal/requirements.txt /tmp/portal-requirements.txt
RUN pip install --no-cache-dir -r /tmp/transport-requirements.txt -r /tmp/portal-requirements.txt

# Ship the existing app and portal unchanged, without local user files.
COPY apps/transport/src apps/transport/src
COPY apps/transport/assets apps/transport/assets
COPY apps/transport/vendor apps/transport/vendor
COPY apps/transport/hosted.py apps/transport/hosted.py
COPY apps/nesting/index.html apps/nesting/index.html
COPY web/portal web/portal
COPY scripts/prepare_transport_assets.py scripts/prepare_transport_assets.py
COPY deploy/render/supervisord.conf deploy/render/supervisord.conf
COPY deploy/render/check_runtime.py deploy/render/check_runtime.py
RUN python scripts/prepare_transport_assets.py \
    && useradd --create-home --uid 10001 flowermoon \
    && mkdir -p /usr/local/novnc /opt/flowermoon/.runtime /opt/flowermoon/apps/transport/data \
    && ln -s /usr/share/novnc /usr/local/novnc/noVNC-packaged \
    && chown -R flowermoon:flowermoon /opt/flowermoon/.runtime /opt/flowermoon/apps/transport/data
USER flowermoon
ENV HOME=/home/flowermoon PORT=8000
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/bin/supervisord", "-c", "/opt/flowermoon/deploy/render/supervisord.conf"]
