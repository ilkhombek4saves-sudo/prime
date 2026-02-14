#!/bin/bash
# Minimal installer - downloads full install.sh from GitHub
set -e
REPO="https://raw.githubusercontent.com/yourusername/prime/main"
echo "Downloading Prime installer..."
curl -fsSL "$REPO/install.sh" -o /tmp/prime-install.sh
bash /tmp/prime-install.sh
