import docker
import argparse
import os
import subprocess

def cleanup_old_images(specific_image_id=None):
    """
    Removes dangling images (untagged and unused) after updates.
    
    Args:
        specific_image_id (str | None): If provided, removes only this specific image.
    """
    client = docker.from_env()
    
    print("\n=== Cleaning up old images ===")
    
    try:
        if specific_image_id:
            # Removes a specific image
            try:
                img = client.images.get(specific_image_id)
                print(f"Removing specific image {img.short_id}...")
                client.images.remove(img.id, force=False)
                print(f"✓ Removed")
            except docker.errors.ImageNotFound:
                print(f"Image {specific_image_id} not found (probably already removed)")
            except docker.errors.APIError as e:
                print(f"✗ Error: {e}")
        else:
            # Removes all dangling images
            dangling_images = client.images.list(filters={'dangling': True})
            
            if not dangling_images:
                print("No dangling images to remove")
                return
            
            print(f"Found {len(dangling_images)} dangling images to remove")
            
            for img in dangling_images:
                try:
                    print(f"  Removing image {img.short_id}...")
                    client.images.remove(img.id, force=False)
                    print(f"  ✓ Removed")
                except docker.errors.APIError as e:
                    print(f"  ✗ Error: {e}")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")

def compose_update_containers(compose_path, compose_file, image_name, service_name, was_running):
    """
    Pulls an image and rebuilds/restarts Docker Compose services.

    Args:
        compose_path (str | None): Working directory for compose commands (fallback: cwd).
        compose_file (str | None): One or more compose files separated by os.pathsep, ":" or ",".
        image_name (str): Image reference to pull (e.g. "repo/image:tag").
        service_name (str): Name of the service inside the compose file.
        was_running (bool): True if the container was running before the update.

    Returns:
        bool: True if successful, False otherwise.
    """
    
    # Working directory (fallback to current cwd)
    cwd = compose_path or os.getcwd()

    # Parse compose files (can be multiple)
    files = []
    if compose_file:
        parts = None
        for sep in (os.pathsep, ":", ","):
            if sep in compose_file:
                parts = compose_file.split(sep)
                break
        if parts is None:
            parts = [compose_file]
        files = [p.strip() for p in parts if p.strip()]
    
    docker_compose_cmd = ["docker", "compose"]
    for f in files:
        docker_compose_cmd += ["-f", f]
    
    # Change working directory to project working_dir if provided
    try:
        old_cwd = os.getcwd()
        os.chdir(cwd)
    except Exception as e:
        print(f"  Unable to change directory to {cwd}: {e}")
        return False
    
    try:
        # Pull updated image
        print(f"  Pulling image {image_name} from registry...")
        pull_cmd = ["docker", "pull", image_name]
        proc = subprocess.run(pull_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(proc.stdout)
        if proc.returncode != 0:
            print(f"  Error: docker pull returned {proc.returncode}")
            return False
        
        # If the container was running, rebuild and restart
        if was_running:
            print(f"  Rebuilding and restarting service '{service_name}'...")
            up_cmd = docker_compose_cmd + ["up", "-d", "--build", service_name]
            proc = subprocess.run(up_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(proc.stdout)
            if proc.returncode != 0:
                print(f"  Error: docker compose up returned {proc.returncode}")
                return False
        else:
            # If the container was stopped, update the image without starting it
            print(f"  Container was stopped. Pulling updated image without starting...")
            pull_cmd = docker_compose_cmd + ["up", "--no-start", service_name]
            proc = subprocess.run(pull_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(proc.stdout)
            if proc.returncode != 0:
                print(f"  Error: docker compose pull returned {proc.returncode}")
                return False
            print(f"  ✓ Image updated, container remains stopped")
        
        return True
            
    finally:
        try:
            os.chdir(old_cwd)
        except Exception:
            pass

def process_container(container, client, force_update=False):
    """Processes a single container to check and apply updates.
    
    Args:
        container: Docker container object.
        client: Docker client.
        force_update (bool): If True, bypass digest check and force update.
        
    Returns:
        tuple: (success: bool, old_image_id: str|None)
    """
    labels = container.labels or {}
    
    # Check if container was created by Docker Compose
    compose_label_keys = ("com.docker.compose.project", "com.docker.compose.service", "com.docker.compose.version")
    if not any(key in labels for key in compose_label_keys):
        print(f"Skip {container.name}: not created by Docker Compose\n")
        return False, None
    
    # Check container state
    container.reload()
    is_running = container.status == 'running'
    status_msg = "running" if is_running else f"stopped ({container.status})"
    
    # Use the specific container image ID instead of the shared image object
    container_image_id = container.attrs['Image']
    
    # Retrieve image by ID
    try:
        image_obj = client.images.get(container_image_id)
    except docker.errors.ImageNotFound:
        print(f"Skip {container.name}: image not found\n")
        return False, None
    
    image_name = image_obj.tags[0] if image_obj.tags else None
    
    if not image_name:
        print(f"Skip {container.name}: no tag\n")
        return False, None
    
    print(f"Container: {container.name} [{status_msg}]")
    print(f"Image: {image_name}")
    print(f"Image ID: {container_image_id[:12]}")
    
    needs_update = False
    
    if force_update:
        print(f"  Force mode: forced update")
        needs_update = True
    else:
        # Local digest (from RepoDigest if available)
        local_digest = image_obj.attrs.get('RepoDigests', [])
        if not local_digest:
            print(f"  No local RepoDigest found\n")
            return False, None

        local_digest = local_digest[0].split('@')[1] if '@' in local_digest[0] else None

        # Remote digest
        try:
            remote_data = client.images.get_registry_data(image_name)
            remote_digest = remote_data.attrs.get('Descriptor', {}).get('digest')
        except Exception as e:
            print(f"  Error: cannot retrieve remote digest: {e}\n")
            return False, None

        # Compare digests
        if local_digest != remote_digest:
            print(f"  Digest mismatch! Updating...")
            needs_update = True
        else:
            print(f"  Already up to date\n")
            return False, None
    
    if needs_update:
        service_name = labels.get('com.docker.compose.service')
        old_image_id = container_image_id
        
        success = compose_update_containers(
            compose_path=labels.get('com.docker.compose.project.working_dir'),
            compose_file=labels.get('com.docker.compose.project.config_files'),
            image_name=image_name,
            service_name=service_name,
            was_running=is_running
        )
        
        if success:
            print(f"  ✓ Updated\n")
            return True, old_image_id
        else:
            print(f"  ✗ Update failed\n")
            return False, None
    
    return False, None

def update_containers(label="autoupdate.enable=true", container_name=None, force=False):
    """
    Checks and updates containers created with Docker Compose.
    
    Args:
        label (str): Label used to filter containers (default: "autoupdate.enable=true").
        container_name (str | None): If provided, updates only this container.
        force (bool): If True, bypasses label check and forces update.
        
    Returns:
        list: List of (container_name, old_image_id) for updated containers.
    """

    # Connect to Docker
    client = docker.from_env()
    updated_containers = []

    # Single-container mode
    if container_name:
        print(f"Single-container update mode: {container_name}")
        print(f"Force mode: {'Yes' if force else 'No'}\n")
        
        try:
            container = client.containers.get(container_name)
        except docker.errors.NotFound:
            print(f"Error: Container '{container_name}' not found")
            return updated_containers
        
        # Check label if not in force mode
        if not force:
            labels = container.labels or {}
            if label not in labels or labels[label] != "true":
                print(f"Error: Container '{container_name}' does not have label '{label}'")
                print(f"Use --force to update anyway")
                return updated_containers
        
        success, old_image_id = process_container(container, client, force_update=force)
        if success and old_image_id:
            updated_containers.append((container_name, old_image_id))
        
        return updated_containers

    # Batch mode
    filters = {"label": label} if not force else {}
    containers = client.containers.list(all=True, filters=filters)

    print(f"Found {len(containers)} containers to check")
    print(f"Force mode: {'Yes' if force else 'No'}\n")

    # Process each container
    for container in containers:
        success, old_image_id = process_container(container, client, force_update=force)
        if success and old_image_id:
            updated_containers.append((container.name, old_image_id))
    
    return updated_containers

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='Auto updater',
        description='Automatically update Docker Compose containers based on image updates in the registry.',
        epilog='Examples:\n'
               '  %(prog)s                                   # Update all containers with label\n'
               '  %(prog)s --update mycontainer              # Update only mycontainer (if has label)\n'
               '  %(prog)s --update mycontainer --force      # Force update mycontainer (bypass label)\n'
               '  %(prog)s --force                           # Force update all containers\n'
               '  %(prog)s --cleanup                         # Update all and cleanup dangling images\n'
               '  %(prog)s --update mycontainer --cleanup    # Update one and cleanup its old image\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--label', type=str, help='Label to filter containers for update', 
                       default='autoupdate.enable=true', required=False)
    parser.add_argument('--update', type=str, metavar='CONTAINER', 
                       help='Update only the specified container name')
    parser.add_argument('--force', action='store_true', 
                       help='Force update bypassing label check (use with --update or alone for all containers)')
    parser.add_argument('--cleanup', action='store_true', 
                       help='Cleanup old images after update (specific image with --update, all dangling otherwise)')
    
    args = parser.parse_args()

    # Argument validation
    if args.force and not args.update:
        print("Warning: --force without --update will update ALL Docker Compose containers regardless of label. Continue? (y/N): ", end='')
        confirm = input().strip().lower()
        if confirm != 'y':
            print("Operation cancelled")
            exit(0)

    # Run updates
    updated = update_containers(label=args.label, container_name=args.update, force=args.force)
    
    # Cleanup
    if args.cleanup:
        if args.update and updated:
            # Targeted cleanup: only the image from the updated container
            _, old_image_id = updated[0]
            cleanup_old_images(specific_image_id=old_image_id)
        elif not args.update:
            # General cleanup: all dangling images
            cleanup_old_images()
        else:
            print("\nNo containers updated, skipping cleanup")
    
    # Summary
    if updated:
        print(f"\n{'='*50}")
        print(f"Summary: {len(updated)} containers updated successfully")
        for name, _ in updated:
            print(f"  ✓ {name}")
    else:
        print(f"\n{'='*50}")
        print("No containers updated")