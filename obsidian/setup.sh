#!/bin/bash
set -e

echo "🐚 Setting up shell integrations for baked-in shims..."

# Path to the baked-in system shims and mise directories
SHIMS_PATH="/usr/local/share/mise/shims"
MISE_DATA_DIR="/usr/local/share/mise"
MISE_CONFIG_DIR="/etc/mise"
MISE_CACHE_DIR="/usr/local/share/mise/cache"

# Bash integration
mkdir -p ~/.bashrc.d
{
    echo "export MISE_DATA_DIR=\"$MISE_DATA_DIR\""
    echo "export MISE_CONFIG_DIR=\"$MISE_CONFIG_DIR\""
    echo "export MISE_CACHE_DIR=\"$MISE_CACHE_DIR\""
    echo "export PATH=\"$SHIMS_PATH:\$PATH\""
} > ~/.bashrc.d/mise.sh

# Nushell integration
mkdir -p ~/.config/nushell
touch ~/.config/nushell/env.nu
if ! grep -q "$SHIMS_PATH" ~/.config/nushell/env.nu; then
    {
        echo "\$env.MISE_DATA_DIR = \"$MISE_DATA_DIR\""
        echo "\$env.MISE_CONFIG_DIR = \"$MISE_CONFIG_DIR\""
        echo "\$env.MISE_CACHE_DIR = \"$MISE_CACHE_DIR\""
        echo "\$env.PATH = (\$env.PATH | prepend \"$SHIMS_PATH\")"
    } >> ~/.config/nushell/env.nu
fi

echo "✅ Shell integrations complete!"
