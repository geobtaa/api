#!/bin/bash
# Setup Elasticsearch Ulimits on Host System
# Run this script on your Kamal server with sudo
#
# Kamal doesn't support ulimits in accessories configuration, so we need to
# configure them at the host system level via Docker daemon configuration.
#
# Usage:
#   sudo bash setup_elasticsearch_ulimits.sh

set -e

echo "Setting up Elasticsearch ulimits..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs to be run with sudo"
    echo "Usage: sudo bash setup_elasticsearch_ulimits.sh"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

# Create /etc/docker directory if it doesn't exist
mkdir -p /etc/docker

# Check if daemon.json already exists
if [ -f /etc/docker/daemon.json ]; then
    echo "Warning: /etc/docker/daemon.json already exists"
    echo "Backing up to /etc/docker/daemon.json.backup"
    cp /etc/docker/daemon.json /etc/docker/daemon.json.backup
    
    # Check if default-ulimits already exists
    if grep -q "default-ulimits" /etc/docker/daemon.json; then
        echo "default-ulimits already configured in daemon.json"
        echo "You may need to manually merge the ulimits configuration"
        exit 0
    fi
    
    # Try to merge (simple approach - append to existing JSON)
    echo "Merging ulimits configuration..."
    # This is a simple merge - for complex JSON, you might want to use jq
    python3 << 'PYTHON_EOF'
import json
import sys

try:
    with open('/etc/docker/daemon.json', 'r') as f:
        config = json.load(f)
except:
    config = {}

if 'default-ulimits' not in config:
    config['default-ulimits'] = {
        'nofile': {
            'Name': 'nofile',
            'Hard': 65536,
            'Soft': 65536
        }
    }
    
    with open('/etc/docker/daemon.json', 'w') as f:
        json.dump(config, f, indent=2)
    print("✓ Merged ulimits into existing daemon.json")
else:
    print("default-ulimits already exists in daemon.json")
PYTHON_EOF
else
    # Create new daemon.json
    echo "Creating /etc/docker/daemon.json..."
    cat > /etc/docker/daemon.json << 'EOF'
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
    echo "✓ Created /etc/docker/daemon.json"
fi

# Also configure system-wide limits
echo "Configuring system-wide limits..."
if ! grep -q "nofile.*65536" /etc/security/limits.conf; then
    cat >> /etc/security/limits.conf << 'EOF'

# Elasticsearch file descriptor limits
* soft nofile 65536
* hard nofile 65536
EOF
    echo "✓ Added limits to /etc/security/limits.conf"
else
    echo "Limits already configured in /etc/security/limits.conf"
fi

# Restart Docker
echo ""
echo "Restarting Docker daemon..."
if systemctl is-active --quiet docker; then
    systemctl restart docker
    echo "✓ Docker daemon restarted"
else
    echo "Warning: Docker daemon is not running"
    echo "Start it with: systemctl start docker"
fi

echo ""
echo "✓ Ulimits configuration complete!"
echo ""
echo "Next steps:"
echo "  1. Restart Elasticsearch: kamal accessory reboot elasticsearch"
echo "  2. Verify ulimits: kamal accessory exec elasticsearch 'ulimit -n'"
echo "     Should show: 65536"
echo ""
echo "Note: If you're logged in as a user, you may need to log out and back in"
echo "      for /etc/security/limits.conf changes to take effect."
