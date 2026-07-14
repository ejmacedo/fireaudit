#!/bin/sh
# FireAudit Agent installer for pfSense
# Usage: FIREAUDIT_API_URL=https://... FIREAUDIT_AGENT_TOKEN=... sh install.sh
#
# Installs agent.py to /usr/local/fireaudit/ and adds a cron job.
# Phase 0 placeholder — functional installation added in Phase 5.

set -e

if [ -z "$FIREAUDIT_API_URL" ] || [ -z "$FIREAUDIT_AGENT_TOKEN" ]; then
  echo "Error: FIREAUDIT_API_URL and FIREAUDIT_AGENT_TOKEN must be set" >&2
  exit 1
fi

INSTALL_DIR="/usr/local/fireaudit"
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/.env" <<EOF
FIREAUDIT_API_URL=$FIREAUDIT_API_URL
FIREAUDIT_AGENT_TOKEN=$FIREAUDIT_AGENT_TOKEN
EOF

chmod 600 "$INSTALL_DIR/.env"

echo "FireAudit agent installed. Add to cron:"
echo "*/5 * * * * root . $INSTALL_DIR/.env && python3 $INSTALL_DIR/agent.py"
