# Distrobox Management

# Bake the base image (the slow part, run once or after config changes)
build:
    podman build -t devbox-base:latest .

# Create the devbox container (ensures image is fresh)
create: build
    distrobox assemble create --name devbox

# Rebuild the devbox container (lightning fast and always up-to-date)
rebuild: build
    distrobox assemble create --replace --name devbox

# Enter the devbox container
enter:
    distrobox enter devbox

# Remove the devbox container
rm:
    distrobox assemble rm --name devbox

# Update tools inside the image (requires a fresh 'build')
update:
    podman build --no-cache -t devbox-base:latest .
