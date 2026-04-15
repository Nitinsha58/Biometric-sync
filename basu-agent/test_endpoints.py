"""
test_endpoints.py — Test the attendance-sync server endpoints.

GET  /attendance-sync/unregistered-users
PATCH /attendance-sync/mark-registered

Run: python test_endpoints.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
import config

BASE = config.SERVER_URL.rstrip("/")
HEADERS = {
    "Content-Type": "application/json",
}

sep = "═" * 62

print(f"\nServer : {BASE}")
print(f"Center : {config.CENTER_ID}\n")

# ── 1. GET unregistered-users ──────────────────────────────────────
print(sep)
print("TEST 1  GET /attendance-sync/unregistered-users")
print(sep)

try:
    r = requests.get(
        f"{BASE}/attendance-sync/unregistered-users",
        headers=HEADERS,
        timeout=10,
    )
    print(f"Status  : {r.status_code}")
    body = r.json()
    print(f"Response:\n{json.dumps(body, indent=2)}")
    r.raise_for_status()
except requests.HTTPError as e:
    print(f"HTTP ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Normalise list — server wraps: {data: {users: [...]}}
users: list = (
    body
    if isinstance(body, list)
    else body.get("data", {}).get("users", [])
)
print(f"\nFound {len(users)} unregistered user(s)")

# ── 2. PATCH mark-registered ───────────────────────────────────────
print(f"\n{sep}")
print("TEST 2  PATCH /attendance-sync/mark-registered")
print(sep)

if not users:
    print("No unregistered users returned — building a minimal synthetic payload.")
    # Send a dummy CUID-shaped id so we can see how the server validates it
    test_payload = {
        "users": [
            {
                "id": "clxxxxxxxxxxxxxxxxxxxxxxxx",   # fake CUID
                "isRegistered": False,
                "isFingerPrintRegistered": False,
            }
        ]
    }
else:
    # Use real ids from the GET response — send isRegistered=False as dry-run
    # so we don't accidentally flip real data
    test_payload = {
        "users": [
            {
                "id": u.get("id", u.get("userId", "")),
                "isRegistered": False,
                "isFingerPrintRegistered": False,
            }
            for u in users[:3]   # cap at 3 for the test
        ]
    }

print(f"Payload:\n{json.dumps(test_payload, indent=2)}\n")

try:
    r2 = requests.patch(
        f"{BASE}/attendance-sync/mark-registered",
        headers=HEADERS,
        json=test_payload,
        timeout=10,
    )
    print(f"Status  : {r2.status_code}")
    try:
        print(f"Response:\n{json.dumps(r2.json(), indent=2)}")
    except Exception:
        print(f"Body    : {r2.text}")
    r2.raise_for_status()
    print("\n✓ Both endpoints reachable and responding correctly.")
except requests.HTTPError as e:
    body_text = ""
    try:
        body_text = e.response.json()
    except Exception:
        body_text = e.response.text
    print(f"HTTP ERROR {e.response.status_code}: {body_text}")
except Exception as e:
    print(f"ERROR: {e}")
