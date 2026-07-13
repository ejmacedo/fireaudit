"""FireAudit Agent — runs on pfSense via cron.

Phase 0: placeholder structure only.
Phase 5+: snapshot push with HMAC signing.
Phase 12+: remote command polling and execution.

Never stores pfSense API key on the backend — used locally only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone


def collect_snapshot() -> dict:
    """Collect firewall state via local pfSense API. Placeholder."""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "pfsense_version": "",
        "rules": [],
        "interfaces": [],
        "certificates": [],
        "vpn": [],
        "system": {},
    }


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def push_snapshot(api_url: str, agent_token: str, snapshot: dict) -> None:
    payload_bytes = json.dumps(snapshot, separators=(",", ":")).encode()
    signature = sign_payload(payload_bytes, agent_token)

    req = urllib.request.Request(
        f"{api_url}/v1/ingest/snapshot",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {agent_token}",
            "X-Signature": signature,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 202):
            raise RuntimeError(f"Unexpected status: {resp.status}")


def poll_commands(api_url: str, agent_token: str) -> dict | None:
    """Poll for pending remote commands. Phase 12+."""
    return None


def main() -> None:
    api_url = os.environ.get("FIREAUDIT_API_URL", "")
    agent_token = os.environ.get("FIREAUDIT_AGENT_TOKEN", "")

    if not api_url or not agent_token:
        print("FIREAUDIT_API_URL and FIREAUDIT_AGENT_TOKEN are required", file=sys.stderr)
        sys.exit(1)

    snapshot = collect_snapshot()
    push_snapshot(api_url, agent_token, snapshot)

    command = poll_commands(api_url, agent_token)
    if command:
        pass


if __name__ == "__main__":
    main()
