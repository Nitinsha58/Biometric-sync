"""
device.py — All pyzk device operations for the BASU Biometric Agent.

ZKDevice wraps every interaction with the eSSL F22 device.
All methods open a fresh connection, perform the operation, then
disconnect — keeping the connection window as small as possible.
"""

import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from zk import ZK
from zk.exception import ZKNetworkError, ZKErrorResponse

import config

logger = logging.getLogger(__name__)

# Global lock — only one ZK connection open at a time.
# Both SyncWorker and dashboard DataLoader threads acquire this.
_device_lock = threading.Lock()


class ZKDevice:
    """Wrapper around pyzk for the BASU agent."""

    def __init__(
        self,
        ip: str = config.DEVICE_IP,
        port: int = config.DEVICE_PORT,
        timeout: int = 5,
    ):
        self.ip = ip
        self.port = port
        self.timeout = timeout

    @contextmanager
    def _connection(self):
        """Open a connection, disable the device for safe read/write, then clean up."""
        with _device_lock:
            zk = ZK(self.ip, port=self.port, timeout=self.timeout, ommit_ping=True)
            conn = None
            try:
                conn = zk.connect()
                conn.disable_device()
                yield conn
            finally:
                if conn:
                    try:
                        conn.enable_device()
                    except Exception:
                        pass
                    try:
                        conn.disconnect()
                    except Exception:
                        pass

    # -----------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------

    def get_info(self) -> dict:
        """
        Return a dict with core device metadata.

        Keys: serial_number, device_name, firmware_version, platform, device_time
        """
        with self._connection() as conn:
            return {
                "serial_number": conn.get_serialnumber(),
                "device_name": conn.get_device_name(),
                "firmware_version": conn.get_firmware_version(),
                "platform": conn.get_platform(),
                "device_time": str(conn.get_time()),
            }

    def get_users_with_fingerprint_status(self) -> list[dict]:
        """
        Return all enrolled users with their fingerprint status.

        Each item: {uid, name, user_id, fingerprint_registered: bool}
        Fingerprint status is derived from whether a template exists for the uid.
        """
        with self._connection() as conn:
            users = conn.get_users()
            templates = conn.get_templates()

            # Build a set of uids that have at least one fingerprint template
            enrolled_uids: set[int] = {t.uid for t in templates}

            return [
                {
                    "uid": u.uid,
                    "name": u.name,
                    "user_id": u.user_id,
                    "fingerprint_registered": u.uid in enrolled_uids,
                }
                for u in users
            ]

    def get_attendance(self) -> list[dict]:
        """
        Return all attendance records stored on the device.

        Each item: {user_id, timestamp (ISO string), punch (0=in, 1=out)}
        """
        with self._connection() as conn:
            records = conn.get_attendance()
            return [
                {
                    "user_id": a.user_id,
                    "timestamp": a.timestamp.isoformat(),
                    "punch": a.punch,
                }
                for a in records
            ]

    # -----------------------------------------------------------------
    # Write operations
    # -----------------------------------------------------------------

    def set_user(self, uid: int, name: str, user_id: str) -> None:
        """
        Create or update a user on the device.

        uid      — integer primary key (must be unique)
        name     — display name (truncated to 24 chars by device limit)
        user_id  — string identifier (usually same as uid)
        """
        with self._connection() as conn:
            conn.set_user(
                uid=uid,
                name=name[:24],
                privilege=0,
                password="",
                user_id=str(user_id),
            )
        logger.info("set_user: uid=%s name=%s", uid, name)

    def delete_user(self, uid: int) -> None:
        """Remove a user from the device by uid."""
        with self._connection() as conn:
            conn.delete_user(uid=uid)
        logger.info("delete_user: uid=%s", uid)

    def clear_attendance(self) -> None:
        """Remove all attendance records from the device."""
        with self._connection() as conn:
            conn.clear_attendance()
        logger.info("clear_attendance: all records removed")

    # -----------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------

    def ping(self) -> bool:
        """
        Return True if the device is reachable, False otherwise.
        Uses a lightweight connection attempt (get_serialnumber) as the probe.
        """
        try:
            with self._connection() as conn:
                conn.get_serialnumber()
            return True
        except (ZKNetworkError, ZKErrorResponse, OSError):
            return False
