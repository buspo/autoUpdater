<div align="center">
  <img src="./img/logo.png" width="450" />

---

A lightweight Python utility that automatically detects and updates Docker Compose services when new image versions are available in the registry!

[![example workflow](https://github.com/buspo/autoUpdater/actions/workflows/CI%20test.yml/badge.svg)](https://github.com/buspo/autoUpdater/actions/workflows/CI%20test.yml/)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io%2Fbuspo%2Fautoupdater-blue)](https://github.com/buspo/autoUpdater/pkgs/container/autoupdater)
</div>

## ⚠️ SECURITY WARNING

> [!WARNING]
> **Docker socket = root access to your entire Docker environment**
> 
> This tool can control ALL containers. A compromise means full system access.
> Review [Security Considerations](#%EF%B8%8F-security-considerations) before installing.

## 🚀 Features

- **Automatic digest comparison**: Detects outdated images by comparing local vs. remote SHA256 digests
- **Compose-aware**: Works with Docker Compose containers (validates via Compose labels)
- **Cron scheduling**: Automated updates on your schedule (daily, hourly, custom)
- **Flexible update modes**: All labeled, single container, or force mode
- **Image cleanup**: Optionally remove old/dangling images after updates
- **State preservation**: Respects container running state during updates
- **Containerized**: Runs as a Docker container with access to host Docker daemon
- **Non-interactive mode**: Automatic confirmation for CI/CD pipelines

## 📋 Table of Contents

- [Security Considerations](#%EF%B8%8F-security-considerations)
- [Installation](#-installation)
  - [Option 1: Pre-built Docker Image (Recommended)](#option-1-pre-built-docker-image-recommended)
  - [Option 2: Standalone Script](#option-2-standalone-script)
  - [Option 3: Build from Source](#option-3-build-from-source)
- [Docker Image Tags](#%EF%B8%8F-docker-image-tag)
- [Usage](#-usage)
  - [Standalone Mode](#standalone-mode)
  - [Container Mode](#container-mode)
- [Configuration](#%EF%B8%8F-configuration)
- [Docker Compose Setup Example](#-docker-compose-setup-example)
- [How It Works](#-how-it-works)
- [Monitoring and Logs](#-monitoring-and-logs)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

---

## ⚠️ Security Considerations

**IMPORTANT: Read this before installing!**

### What It Needs
- The service needs access to the Docker socket (`/var/run/docker.sock`)
- **Container mode**: Runs as root inside container (isolated from host)
- **Standalone mode**: User must be in the `docker` group (non-root)

### Security Implications

- The autoupdate container has full control over Docker daemon
- Use registry credentials via Docker config for private registries
- Recommend mounting compose directories as read-only (`:ro`)
- Always test in development before production use

### Security Best Practices

1. **Don't auto-update critical services**: Exclude databases and stateful services from auto-updates
2. **Use specific tags**: Prefer `nginx:1` over `nginx:latest` for more control
3. **Monitor logs**: Regularly check update logs for issues
4. **Test first**: Use `RUN_ON_STARTUP=true` to test immediately
5. **Backup**: Always backup before enabling auto-updates on production

---

## 📥 Installation

### Option 1: Pre-built Docker Image (Recommended)

Pull the latest stable image from GitHub Container Registry:

```bash
# Pull latest stable release
docker pull ghcr.io/buspo/autoupdater:latest

# Or pull development version
docker pull ghcr.io/buspo/autoupdater:dev
```

Then create your `docker-compose.yml`:

```yaml
services:
  autoupdate:
    image: ghcr.io/buspo/autoupdater:latest
    container_name: autoupdate
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /opt/docker:/opt/docker:ro  # Your compose files
    environment:
      - CRON_SCHEDULE=0 3 * * *
      - AUTOUPDATE_LABEL=autoupdate.enable=true
      - AUTO_CLEANUP=true
    labels:
      - autoupdater.self=true
```

Start the service:

```bash
docker compose up -d
```

### Option 2: Standalone Script

```bash
# Clone the repository
git clone https://github.com/buspo/autoUpdater.git
cd autoUpdater

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Option 3: Build from Source

```bash
# Clone the repository
git clone https://github.com/buspo/autoUpdater.git
cd autoUpdater

# Build the image
docker build -t autoupdate:local .

# Or use docker compose
docker compose build

# Start
docker compose up -d
```

---

## 🏷️ Docker Image Tags

Images are available on GitHub Container Registry:

| Tag | Description | Use Case | Update Frequency |
|-----|-------------|----------|------------------|
| `latest` | Latest stable release | **Production** | On each release |
| `stable` | Alias for `latest` | **Production** | On each release |
| `dev` | Latest development build | **Testing/Staging** | On each main branch commit |
| `X.Y.Z` | Specific version (e.g., `0.1.0`) | **Production** (pinned) | Never (immutable) |
| `X.Y` | Latest patch of minor version (e.g., `0.1`) | **Production** (auto-patch) | On patch releases (0.1.x) |
| `X` | Latest minor of major version (e.g., `0`) | **Staging** | On minor/patch releases |
| `dev-abc1234` | Specific commit from dev | **Debug/Testing** | Never (immutable) |

### Examples

```bash
# Production - Latest stable (recommended)
docker pull ghcr.io/buspo/autoupdater:latest

# Production - Specific version (most stable)
docker pull ghcr.io/buspo/autoupdater:0.1.0

# Production - Auto-patch updates
docker pull ghcr.io/buspo/autoupdater:0.1

# Staging/Testing - Latest development
docker pull ghcr.io/buspo/autoupdater:dev

# Debug - Specific commit
docker pull ghcr.io/buspo/autoupdater:dev-a1b2c3d
```

### Tag Selection Guide

```yaml
# For production (most stable)
image: ghcr.io/buspo/autoupdater:0.1.0  # Pinned version

# For production (with auto-patch)
image: ghcr.io/buspo/autoupdater:0.1    # Gets 0.1.1, 0.1.2, etc.

# For production (always latest)
image: ghcr.io/buspo/autoupdater:latest # Gets new releases

# For staging/testing
image: ghcr.io/buspo/autoupdater:dev    # Latest development
```

---

## 🎯 Usage

### Standalone Mode

The standalone mode requires manual execution or setup with cron/systemd.

#### Basic Commands

```bash
# Update all containers with default label
python3 autoupdate.py

# Update a specific container
python3 autoupdate.py --update myapp

# Update and cleanup old images
python3 autoupdate.py --cleanup

# Show all options
python3 autoupdate.py --help
```

#### Arguments Reference

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--label LABEL` | - | `autoupdate.enable=true` | Label filter to identify containers for update |
| `--update CONTAINER` | - | `None` | Update only the specified container name |
| `--force` | - | `False` | Force update bypassing label and digest checks |
| `--cleanup` | - | `False` | Remove old/dangling images after update |
| `--yes` | `-y` | `False` | Automatic yes to prompts (non-interactive mode) |

#### Examples

```bash
# Update all labeled containers and cleanup
python3 autoupdate.py --cleanup

# Update only one container
python3 autoupdate.py --update web

# Force update without label check
python3 autoupdate.py --update app --force

# Force update all with automatic confirmation (for scripts/CI)
python3 autoupdate.py --force --yes

# Use custom label
python3 autoupdate.py --label "myapp.autoupdate=enabled"

# Non-interactive mode for cron jobs
python3 autoupdate.py --cleanup --yes
```

#### Cron Setup (Optional)

```bash
# Edit crontab
crontab -e

# Add line (runs daily at 3 AM)
0 3 * * * cd /path/to/autoUpdater && .venv/bin/python3 autoupdate.py --cleanup --yes >> /var/log/autoupdate.log 2>&1
```

### Container Mode

The containerized version runs automatically on a cron schedule.

#### Quick Start with Pre-built Image

```bash
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
services:
  autoupdate:
    image: ghcr.io/buspo/autoupdater:latest
    container_name: autoupdate
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /opt/docker:/opt/docker:ro
    environment:
      - CRON_SCHEDULE=0 3 * * *
      - AUTO_CLEANUP=true
    labels:
      - autoupdater.self=true
EOF

# Start
docker compose up -d

# View logs
docker compose logs -f
```

#### Direct Docker Commands

```bash
# Pull latest
docker pull ghcr.io/buspo/autoupdater:latest

# Run with docker run
docker run -d \
  --name autoupdate \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/docker:/opt/docker:ro \
  -e CRON_SCHEDULE="0 3 * * *" \
  -e AUTO_CLEANUP=true \
  --label autoupdater.self=true \
  ghcr.io/buspo/autoupdater:latest

# View logs
docker logs -f autoupdate

# Stop
docker stop autoupdate

# Remove
docker rm autoupdate
```

#### Management Commands

```bash
# Check status
docker ps --filter name=autoupdate

# View configuration
docker exec autoupdate env | grep -E "CRON|LABEL|CLEANUP"

# Run update manually
docker exec autoupdate python3 /app/autoupdate.py

# View cron schedule
docker exec autoupdate crontab -l

# Follow logs
docker logs -f autoupdate
```

---

## ⚙️ Configuration

### Container Configuration

Edit `docker-compose.yml` to customize:

#### 1. Mount your Docker Compose directories

```yaml
volumes:
  # Required
  - /var/run/docker.sock:/var/run/docker.sock
  
  # For private registries (optional)
  - $HOME/.docker/config.json:/root/.docker/config.json:ro
  
  # Your compose file directories (add all paths)
  - /opt/docker:/opt/docker:ro
  - /home/user/projects:/projects:ro
  - /srv/apps:/apps:ro
```

#### 2. Configure environment variables

```yaml
environment:
  # Cron schedule (when to run updates)
  # Format: minute hour day month weekday
  - CRON_SCHEDULE=0 3 * * *  # Daily at 3 AM
  
  # Examples:
  # - CRON_SCHEDULE=0 */6 * * *     # Every 6 hours
  # - CRON_SCHEDULE=30 2 * * 0      # Sundays at 2:30 AM
  # - CRON_SCHEDULE=0 0 1 * *       # First day of month
  
  # Label to filter containers
  - AUTOUPDATE_LABEL=autoupdate.enable=true
  
  # Auto cleanup old images after update
  - AUTO_CLEANUP=true
  
  # Force update all containers (bypass label check)
  # WARNING: Use with caution!
  - FORCE_UPDATE=false
  
  # Run update immediately on container startup
  # Useful for testing
  - RUN_ON_STARTUP=false
  
  # Timezone for logs and cron schedule
  - TZ=Europe/Rome
```

---

## 🐳 Docker Compose Setup Example

Label your services to enable auto-updates:

```yaml
services:
  # Web application - will be auto-updated
  web:
    image: nginx:latest
    labels:
      - autoupdate.enable=true  # ← Enable auto-update
    ports:
      - "80:80"
    restart: unless-stopped

  # Application server - will be auto-updated
  app:
    image: myapp:latest
    labels:
      - autoupdate.enable=true  # ← Enable auto-update
    environment:
      - ENV=production
    restart: unless-stopped
      
  # Database - NOT auto-updated (no label)
  database:
    image: postgres:15
    # No autoupdate label - this is intentional!
    # Databases should be updated manually
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: unless-stopped

  # Auto-updater service
  autoupdate:
    image: ghcr.io/buspo/autoupdater:latest
    container_name: autoupdate
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /opt/docker:/opt/docker:ro
    environment:
      - CRON_SCHEDULE=0 3 * * *
      - AUTO_CLEANUP=true
    labels:
      # Prevent self-update
      - autoupdater.self=true
      - autoupdate.enable=false

volumes:
  db-data:
```

Then start your stack:

```bash
docker compose up -d
```

The autoupdate service will:
- Run immediately on startup (if `RUN_ON_STARTUP=true`)
- Run on the configured cron schedule
- Update only services with the label
- Preserve running state of containers
- Optionally cleanup old images

---

## 🔄 How It Works

```
1. Scan Docker containers for Compose metadata labels
2. For each labeled (or specified) container:
   ├─ Retrieve the local image's RepoDigest (SHA256)
   ├─ Query the registry for the remote digest
   └─ Compare digests to detect if update is available
3. If update needed:
   ├─ Pull the new image from registry
   ├─ Run `docker compose up -d --build` (if was running)
   │  OR `docker compose up --no-start` (if was stopped)
   └─ Optionally cleanup the old image (if AUTO_CLEANUP=true)
4. Log all actions with timestamps
```

### Container State Preservation

- **Running containers**: Pulled, rebuilt, and restarted
- **Stopped containers**: Image updated but container remains stopped
- **Labels respected**: Only updates containers with the configured label (unless `--force`)
- **Self-protection**: Skips containers with `autoupdater.self=true` label

---

## 📊 Monitoring and Logs

### View Logs

```bash
# Docker Compose
docker compose logs -f autoupdate

# Docker
docker logs -f autoupdate

# Inside container
docker exec autoupdate tail -f /var/log/autoupdate/autoupdate.log
```

### Health Check

```bash
# Check health status
docker inspect autoupdate --format='{{.State.Health.Status}}'

# Check if cron is running
docker exec autoupdate ps aux | grep cron
```

### Verify Updates

```bash
# List containers with autoupdate label
docker ps -a --filter "label=autoupdate.enable=true" \
  --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```

---

## 🔧 Troubleshooting

### Container not updating

1. **Check label**: Ensure container has `autoupdate.enable=true`
   ```bash
   docker inspect <container> --format '{{.Config.Labels}}'
   ```

2. **Check logs**: Look for errors
   ```bash
   docker logs autoupdate
   ```

3. **Test manually**: Run update check
   ```bash
   docker exec autoupdate python3 /app/autoupdate.py
   ```

### Private registry authentication

Mount your Docker config:

```yaml
volumes:
  - $HOME/.docker/config.json:/root/.docker/config.json:ro
```

Or login before running:

```bash
docker login ghcr.io
```

### Cron not executing

1. **Verify cron is configured**:
   ```bash
   docker exec autoupdate crontab -l
   ```

2. **Check cron is running**:
   ```bash
   docker exec autoupdate ps aux | grep cron
   ```

3. **Test the cron script**:
   ```bash
   docker exec autoupdate /app/run_cron_update.sh
   ```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---