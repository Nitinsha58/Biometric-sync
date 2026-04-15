"""
clean_device.py — Wipe all users and attendance records from the device.

Prompts for confirmation before doing anything destructive.

Run: python clean_device.py [--users] [--attendance] [--all]

  --users       delete all enrolled users (and their fingerprint templates)
  --attendance  clear all attendance logs
  --all         both of the above (default when no flag is given)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from zk import ZK
from zk.exception import ZKNetworkError
import config


def _connect():
    zk = ZK(config.DEVICE_IP, port=config.DEVICE_PORT, timeout=5, ommit_ping=True)
    conn = zk.connect()
    # Do NOT disable_device — some firmware rejects CMD_DELETE_USER while disabled
    return zk, conn


def confirm(prompt: str) -> bool:
    ans = input(f"{prompt} [yes/no]: ").strip().lower()
    return ans == "yes"


def clear_attendance(conn):
    print("  Clearing attendance logs...", end=" ", flush=True)
    conn.clear_attendance()
    print("done.")


def clear_users(conn):
    users = conn.get_users()
    total = len(users)
    if total == 0:
        print("  No users on device — nothing to delete.")
        return
    print(f"  Deleting {total} user(s) + fingerprint templates via clear_data...", end=" ", flush=True)
    conn.clear_data()
    print("done.")
    # Verify
    remaining = conn.get_users()
    if remaining:
        print(f"  clear_data left {len(remaining)} users — falling back to per-uid deletion...")
        failed = 0
        for i, u in enumerate(remaining, 1):
            try:
                conn.delete_user(uid=u.uid)
                print(f"    [{i}/{len(remaining)}] deleted uid={u.uid} name={u.name!r}")
            except Exception as e:
                print(f"    [{i}/{len(remaining)}] FAILED uid={u.uid}: {e}")
                failed += 1
        if failed:
            print(f"  Warning: {failed} user(s) could not be deleted.")
        else:
            print("  All users deleted.")
    else:
        print(f"  Verified: device has 0 users.")


def main():
    parser = argparse.ArgumentParser(description="Wipe device users and/or attendance.")
    parser.add_argument("--users",      action="store_true", help="Delete all users")
    parser.add_argument("--attendance", action="store_true", help="Clear attendance logs")
    parser.add_argument("--all",        action="store_true", help="Both users and attendance")
    args = parser.parse_args()

    do_users      = args.users or args.all or not (args.users or args.attendance)
    do_attendance = args.attendance or args.all or not (args.users or args.attendance)

    print(f"\nDevice  : {config.DEVICE_IP}:{config.DEVICE_PORT}")
    print(f"Actions : {'users + fingerprints  ' if do_users else ''}{'attendance logs' if do_attendance else ''}\n")

    what = []
    if do_users:
        what.append("ALL USERS and fingerprint templates")
    if do_attendance:
        what.append("ALL ATTENDANCE records")

    warning = "  ⚠  This will permanently delete " + " AND ".join(what) + "."
    print(warning)
    if not confirm("\nAre you sure you want to continue?"):
        print("Aborted.")
        sys.exit(0)

    print(f"\nConnecting to device at {config.DEVICE_IP}:{config.DEVICE_PORT}...")
    try:
        zk, conn = _connect()
    except ZKNetworkError as e:
        print(f"ERROR: Could not reach device — {e}")
        sys.exit(1)

    try:
        if do_attendance:
            clear_attendance(conn)
        if do_users:
            clear_users(conn)
        print("\n✓ Device cleaned successfully.")
        print("\n⚠  If the BASU agent is running, stop it now (or it will re-sync users within 30s).")
    except Exception as e:
        print(f"\nERROR during wipe: {e}")
        sys.exit(1)
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
