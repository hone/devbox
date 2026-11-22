# Distrobox Management
default_env := 'devbox'

# Pull the latest prebuilt CI image from GHCR
pull env=default_env:
    podman pull ghcr.io/hone/{{env}}:latest

# Create the container from the prebuilt GHCR image
create env=default_env:
    distrobox assemble create --file {{env}}/distrobox.ini --name {{env}}

# Rebuild the container from the prebuilt GHCR image
rebuild env=default_env:
    distrobox assemble create --file {{env}}/distrobox.ini --replace --name {{env}}

# Local escape hatch: build the image on the host
build env=default_env:
    podman build --pull -t {{env}}-base:latest {{env}}

# Private helper: assemble from a locally built image without mutating distrobox.ini
_assemble-local env extra_args="":
    #!/usr/bin/env bash
    set -euo pipefail
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    sed -e 's|^image=.*|image=localhost/{{env}}-base:latest|' -e 's|^pull=.*|pull=false|' {{env}}/distrobox.ini > "$tmp"
    distrobox assemble create --file "$tmp" {{extra_args}} --name {{env}}

# Local escape hatch: build locally and create the container without mutating distrobox.ini
create-local env=default_env: (build env) (_assemble-local env "")

# Local escape hatch: build locally and replace the container without mutating distrobox.ini
rebuild-local env=default_env: (build env) (_assemble-local env "--replace")

# Enter the devbox container
enter env=default_env:
    distrobox enter {{env}}

# Remove the devbox container
rm env=default_env:
    distrobox assemble rm --file {{env}}/distrobox.ini --name {{env}}

# Local escape hatch: uncached rebuild of the image on the host
update env=default_env:
    podman build --no-cache -t {{env}}-base:latest {{env}}

# Start PostgreSQL server inside the devbox (initializes DB cluster if it doesn't exist)
pg-start:
    @distrobox enter devbox -- bash -c '[ -d ~/.local/share/postgres/data ] || (mkdir -p ~/.local/share/postgres && initdb -D ~/.local/share/postgres/data && echo "unix_socket_directories = '\''/tmp'\''" >> ~/.local/share/postgres/data/postgresql.conf)'
    distrobox enter devbox -- pg_ctl -D ~/.local/share/postgres/data -o "-k /tmp" -l ~/.local/share/postgres/logfile start

# Stop PostgreSQL server inside the devbox
pg-stop:
    distrobox enter devbox -- pg_ctl -D ~/.local/share/postgres/data stop

# Check PostgreSQL server status
pg-status:
    distrobox enter devbox -- pg_ctl -D ~/.local/share/postgres/data status
