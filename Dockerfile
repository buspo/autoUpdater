FROM python:3.11-slim

LABEL maintainer="https://github.com/buspo"
LABEL description="Docker Auto-Updater with cron scheduling"
LABEL version="1.0.0"

RUN apt-get update && apt-get install -y \
    docker.io \
    cron \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -SL https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64 \
    -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose

RUN pip install --no-cache-dir docker

WORKDIR /app

COPY autoupdate.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh


ENV CRON_SCHEDULE="0 2 * * *" \
    AUTOUPDATE_LABEL="autoupdate.enable=true" \
    AUTO_CLEANUP="false" \
    FORCE_UPDATE="false" \
    RUN_ON_STARTUP="false" \
    TZ="Europe/Rome"


RUN mkdir -p /var/log/autoupdate


HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import docker; docker.from_env().ping()" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
