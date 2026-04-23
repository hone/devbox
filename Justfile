# Distrobox Management
default_env := 'devbox'

# Bake the base image (the slow part, run once or after config changes)
build env=default_env:
    podman build -t {{env}}-base:latest {{env}}

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
