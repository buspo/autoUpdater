FROM python:3.11-slim

LABEL maintainer="https://github.com/buspo"
LABEL description="Docker Auto-Updater with cron scheduling"
LABEL version="0.1.0"

RUN apt-get update

RUN apt update
RUN apt install -y ca-certificates curl
RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
RUN chmod a+r /etc/apt/keyrings/docker.asc

COPY <<EOF /etc/apt/sources.list.d/docker.sources
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
 
RUN apt update
RUN apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

RUN apt-get install -y \
    cron \
    curl \
    && rm -rf /var/lib/apt/lists/*
    
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY autoupdate.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh


ENV CRON_SCHEDULE="0 3 * * *" \
    AUTOUPDATE_LABEL="autoupdate.enable=true" \
    AUTO_CLEANUP="false" \
    FORCE_UPDATE="false" \
    RUN_ON_STARTUP="false" \
    TZ="Europe/Rome"


RUN mkdir -p /var/log/autoupdate


HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import docker; docker.from_env().ping()" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
