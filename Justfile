# Distrobox Management
default_env := 'devbox'

# Bake the base image (the slow part, run once or after config changes)
build env=default_env:
    podman build --pull -t {{env}}-base:latest {{env}}

# Create the devbox container (ensures image is fresh)
create env=default_env: (build env)
    distrobox assemble create --file {{env}}/distrobox.ini --name {{env}}

# Rebuild the devbox container (lightning fast and always up-to-date)
rebuild env=default_env: (build env)
    distrobox assemble create --file {{env}}/distrobox.ini --replace --name {{env}}

# Enter the devbox container
enter env=default_env:
    distrobox enter {{env}}

# Remove the devbox container
rm env=default_env:
    distrobox assemble rm --file {{env}}/distrobox.ini --name {{env}}

# Update tools inside the image (requires a fresh 'build')
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

