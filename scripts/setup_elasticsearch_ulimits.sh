#!/bin/bash
"""
Setup Elasticsearch Ulimits on Host System

Kamal doesn't support ulimits in accessories configuration, so we need to
configure them at the host system level or via Docker daemon configuration.

This script helps set up ulimits for the Elasticsearch container.

Usage:
  # On the Kamal server
  kamal ssh
  # Then run this script or follow the manual steps below
"""

set -e

echo "Setting up Elasticsearch ulimits..."

# Option 1: Configure Docker daemon (recommended)
# Add to /etc/docker/daemon.json:
cat << 'EOF' | sudo tee -a /etc/docker/daemon.json > /dev/null || true
{
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  }
}
EOF

# Restart Docker daemon
echo "Restarting Docker daemon..."
sudo systemctl restart docker

# Option 2: Configure systemd service limits (if using systemd)
# This is done automatically by the Docker service, but you can also set it explicitly:
if [ -f /etc/systemd/system/docker.service ]; then
    echo "Configuring systemd limits..."
    sudo mkdir -p /etc/systemd/system/docker.service.d
    cat << 'EOF' | sudo tee /etc/systemd/system/docker.service.d/override.conf
[Service]
LimitNOFILE=65536
EOF
    sudo systemctl daemon-reload
    sudo systemctl restart docker
fi

# Option 3: Configure limits for the deploy user
echo "Configuring user limits..."
cat << 'EOF' | sudo tee -a /etc/security/limits.conf
# Elasticsearch file descriptor limits
* soft nofile 65536
* hard nofile 65536
EOF

echo ""
echo "✓ Ulimits configuration complete!"
echo ""
echo "To verify:"
echo "  1. Restart Elasticsearch: kamal accessory reboot elasticsearch"
echo "  2. Check ulimits: kamal accessory exec elasticsearch 'ulimit -n'"
echo "     Should show: 65536"
echo ""
echo "Note: You may need to log out and back in for user limits to take effect."

