"""
test_phase1.py — Phase 1 test driver.

Connects to the device, reads all data, pretty-prints it locally,
then POSTs each payload to the configured server_url (webhook.site).

Usage:
    cd basu-agent
    python test_phase1.py

Before running:
    1. Edit config.json — replace server_url with your webhook.site URL.
    2. Make sure the device is reachable on the LAN (ethernet, not WiFi).
"""

import json
import sys
import logging
from pathlib import Path

# Allow running directly from basu-agent/ or from repo root
sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: E402 — must come after sys.path patch
from device import ZKDevice
from api import APIClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SEP = "─" * 60


def _pp(label: str, data) -> None:
    print(f"\n{SEP}")
    print(f"  {label}")
    print(SEP)
    print(json.dumps(data, indent=2, default=str))


def main():
    log.info("Starting Phase 1 test")
    log.info("Device: %s:%s", config.DEVICE_IP, config.DEVICE_PORT)
    log.info("Server URL: %s", config.SERVER_URL)

    device = ZKDevice()
    api = APIClient()

    # ------------------------------------------------------------------
    # 1. Device info
    # ------------------------------------------------------------------
    log.info("Reading device info...")
    info = device.get_info()
    _pp("1. DEVICE INFO", info)

    log.info("POSTing device info → /api/biometric/device/info")
    try:
        resp = api.post_device_info(info)
        log.info("Response: %s", resp)
    except Exception as e:
        log.error("POST device info failed: %s", e)

    # ------------------------------------------------------------------
    # 2. Student / fingerprint status
    # ------------------------------------------------------------------
    log.info("Reading users + fingerprint status...")
    students = device.get_users_with_fingerprint_status()
    _pp("2. STUDENT STATUS", students)

    log.info("POSTing student status → /api/biometric/students/status")
    try:
        resp = api.post_student_status(students)
        log.info("Response: %s", resp)
    except Exception as e:
        log.error("POST student status failed: %s", e)

    # ------------------------------------------------------------------
    # 3. Attendance logs
    # ------------------------------------------------------------------
    log.info("Reading attendance logs...")
    attendance = device.get_attendance()
    _pp("3. ATTENDANCE LOGS", attendance)
    log.info("Total records: %d", len(attendance))

    log.info("POSTing attendance → /api/biometric/attendance/sync")
    try:
        resp = api.post_attendance(attendance)
        log.info("Response: %s", resp)
    except Exception as e:
        log.error("POST attendance failed: %s", e)

    # ------------------------------------------------------------------
    # 4. Pending commands (read-only poll — expects empty list for now)
    # ------------------------------------------------------------------
    log.info("Polling pending commands → /api/biometric/commands/pending")
    try:
        commands = api.get_pending_commands()
        _pp("4. PENDING COMMANDS", commands)
    except Exception as e:
        log.error("GET pending commands failed: %s", e)

    print(f"\n{SEP}")
    print("  Phase 1 complete. Check webhook.site for the 3 POST requests.")
    print(SEP)


if __name__ == "__main__":
    main()
