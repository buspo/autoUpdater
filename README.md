# AutoUpdater for Docker Compose

A lightweight Python utility that automatically detects and updates Docker Compose services when new image versions are available in the registry. It compares local image digests with remote registry digests to determine if updates are needed.

## Installation

```bash
# Clone the repository
git clone https://github.com/buspo/autoUpdater.git
cd autoUpdater

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Features

- **Automatic digest comparison**: Detects outdated images by comparing local vs. remote SHA256 digests
- **Compose-aware**: Works exclusively with Docker Compose containers (validates via Compose labels)
- **Flexible update modes**: All labeled, single container, or force mode
- **Image cleanup**: Optionally remove old/dangling images after updates
- **State preservation**: Respects container running state during updates

## Usage

### Basic Commands

```bash
# Update all containers with default label
python3 main.py

# Update a specific container
python3 main.py --update myapp

# Update and cleanup old images
python3 main.py --cleanup

# Show all options
python3 main.py --help
```

### Arguments Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--label LABEL` | `autoupdate.enable=true` | Label filter to identify containers for update |
| `--update CONTAINER` | `None` | Update only the specified container name (bypasses label filter) |
| `--force` | `False` | Force update bypassing label and digest checks; requires confirmation when used alone |
| `--cleanup` | `False` | Remove old/dangling images after update |

### Examples

**Update all labeled containers and cleanup dangling images:**
```bash
python3 main.py --cleanup
```

**Update only one container:**
```bash
python3 main.py --update web
```

**Force update a specific container (no label check):**
```bash
python3 main.py --update app --force
```

**Use a custom label:**
```bash
python3 main.py --label "myapp.autoupdate=enabled"
```

**Force update all containers (requires confirmation):**
```bash
python3 main.py --force
```

## How It Works

```
1. Scans Docker containers for Compose metadata labels
2. For each labeled (or specified) container:
   - Retrieves the local image's RepoDigest
   - Queries the registry for the remote digest
   - Compares digests to detect updates
3. If update needed:
   - Pulls the new image from registry
   - Runs `docker compose up --build` (or `--no-start` if stopped)
   - Optionally cleans up the old image
```

## Docker Compose Setup Example

To make containers eligible for auto-update, label them in your `docker-compose.yml`:

```yaml
version: '3.8'

services:
  web:
    image: myapp1:latest
    labels:
      - autoupdate.enable=true  # Enable auto-update for this service
    ports:
      - "80:80"

  app:
    image: myapp2:latest
    labels:
      - autoupdate.enable=true  # Enable auto-update for this service
    environment:
      - ENV=production
      
  database:
    image: myapp3:15
    # No label - this service will NOT be automatically updated
```

Run your stack:
```bash
docker-compose up -d
```

Then scan for updates:
```bash
python3 main.py
```

The application will:
- Detect the labeled services
- Check if new image versions are available in the registry
- Pull and restart only services with updated images
- Leave unlabeled services untouched

## Security Notes

- The service needs access to the Docker socket
- **Non-root setup**: User must be in the `docker` group
- **Root setup**: Service runs as root (simpler but less secure)
- Use registry credentials via Docker config when pulling from private registries
