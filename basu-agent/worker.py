"""
worker.py — Background sync thread for the BASU Biometric Agent.

Runs every SYNC_INTERVAL seconds:
  1. Connect to device
  2. GET pending commands from server
  3. Execute each command (sync_user / delete_user) on the device
  4. ACK each command to server
  5. POST fingerprint status for all enrolled users
  6. Disconnect

Exposes `device_online` and `last_sync_time` for the dashboard.
All activity is written to agent.log via a rotating file handler.
"""

import logging
import sys
import threading
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from zk.exception import ZKNetworkError, ZKErrorResponse

import config
import db
from api import APIClient
from device import ZKDevice

# ------------------------------------------------------------------
# Logging setup  (LOG_PATH resolves to AppData in frozen builds)
# ------------------------------------------------------------------
LOG_PATH = config.LOG_PATH

_file_handler = RotatingFileHandler(
    LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
)

# Attach to root so all modules (device, api) log here too
root_logger = logging.getLogger()
if not root_logger.handlers:
    root_logger.addHandler(logging.StreamHandler(sys.stdout))
root_logger.addHandler(_file_handler)
root_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAY = 5  # seconds between retries on network error


class SyncWorker(threading.Thread):
    """
    Background thread that polls the device and server on a fixed interval.

    Attributes
    ----------
    device_online : bool
        True if the last sync cycle reached the device successfully.
    server_reachable : bool
        True if the last sync cycle successfully contacted the API server.
    last_sync_time : Optional[datetime]
        Timestamp of the last completed sync cycle (None until first run).
    last_error : Optional[str]
        Human-readable description of the last error, if any.
    """

    def __init__(self):
        super().__init__(name="SyncWorker", daemon=True)
        self.device_online: bool = False
        self.server_reachable: bool = False
        self.last_sync_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.syncing: bool = False

        # Data caches — dashboard reads these without hitting the device
        self._cached_students: list[dict] = []
        self._cached_device_info: dict = {}
        self._next_sync_at: Optional[datetime] = None

        self._stop_event = threading.Event()
        self._device = ZKDevice()
        self._api = APIClient()

        # Lock protects the public attributes when read by the dashboard thread
        self._lock = threading.Lock()

        db.init_db()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def next_sync_in(self) -> int:
        """Seconds remaining until the next automatic sync cycle (0 if unknown)."""
        with self._lock:
            if self._next_sync_at is None:
                return 0
            remaining = (self._next_sync_at - datetime.now()).total_seconds()
            return max(0, int(remaining))

    def stop(self):
        """Signal the worker to stop after the current cycle finishes."""
        self._stop_event.set()

    def run_once(self):
        """Trigger a single sync cycle immediately (called by Sync Now button)."""
        threading.Thread(
            target=self._sync_cycle, name="ManualSync", daemon=True
        ).start()

    def reload_config(self) -> None:
        """Re-read config.json and restart the device / API client with new settings.

        Called by the dashboard Settings page after saving so changes take
        effect immediately without restarting the agent process.
        """
        import config as _c
        _c.reload()
        with self._lock:
            self._device = ZKDevice()
            self._api    = APIClient()
        logger.info(
            "Config reloaded — device=%s:%s  server=%s",
            _c.DEVICE_IP, _c.DEVICE_PORT, _c.SERVER_URL,
        )

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self):
        logger.info("SyncWorker started (interval=%ss)", config.SYNC_INTERVAL)
        while not self._stop_event.is_set():
            self._sync_cycle()
            # Record when the next automatic cycle will fire
            next_at = datetime.now() + timedelta(seconds=config.SYNC_INTERVAL)
            with self._lock:
                self._next_sync_at = next_at
            # Sleep in small chunks so stop() is responsive
            for _ in range(config.SYNC_INTERVAL * 2):
                if self._stop_event.is_set():
                    break
                time.sleep(0.5)
        logger.info("SyncWorker stopped")

    # ------------------------------------------------------------------
    # Core sync cycle
    # ------------------------------------------------------------------

    def _sync_cycle(self):
        logger.info("─── Sync cycle starting ───")
        with self._lock:
            self.syncing = True
        try:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    self._do_sync()
                    with self._lock:
                        self.device_online = True
                        self.last_sync_time = datetime.now()
                        self.last_error = None
                    logger.info("─── Sync cycle complete ───")
                    return
                except (ZKNetworkError, ZKErrorResponse, OSError) as exc:
                    logger.warning(
                        "Device unreachable (attempt %d/%d): %s", attempt, _MAX_RETRIES, exc
                    )
                    if attempt < _MAX_RETRIES:
                        time.sleep(_RETRY_DELAY)
                except Exception as exc:
                    logger.exception("Unexpected error in sync cycle: %s", exc)
                    with self._lock:
                        self.device_online = False
                        self.last_error = str(exc)
                    return

            # All retries exhausted
            with self._lock:
                self.device_online = False
                self.last_error = "Device unreachable after %d attempts" % _MAX_RETRIES
            logger.error(self.last_error)
        finally:
            with self._lock:
                self.syncing = False

    def _do_sync(self):
        _server_ok = False

        # 0. Flush any pending fingerprint-enrollment reports to the server.
        #    If the server is unreachable the flags stay set and are retried next cycle.
        pending_fp = db.get_fp_pending_users()
        if pending_fp:
            fp_statuses = [
                {
                    "id": u["user_id"],
                    "isRegistered": True,
                    "isFingerPrintRegistered": True,
                }
                for u in pending_fp
            ]
            try:
                self._api.mark_users_registered(fp_statuses)
                db.clear_fp_pending([u["user_id"] for u in pending_fp])
                logger.info("Flushed %d pending FP enrollment(s) to server", len(pending_fp))
                _server_ok = True
            except Exception as exc:
                logger.warning("Could not flush pending FP enrollments (will retry): %s", exc)

        # 1. Fetch users not yet registered on device
        unregistered = []
        try:
            unregistered = self._api.get_unregistered_users()
            _server_ok = True
            logger.info("Unregistered users from server: %d", len(unregistered))
        except Exception as exc:
            logger.warning("Could not fetch unregistered users: %s", exc)

        # 2. Sync each unregistered user onto the device and persist to local DB.
        for user in unregistered:
            cuid = user.get("id", "")
            name = (user.get("name") or "Unknown")[:24]
            device_uid = int(user["biometricNumber"])
            try:
                self._device.set_user(uid=device_uid, name=name, user_id=str(device_uid))
                db.upsert_user(
                    biometric_number=device_uid,
                    user_id=cuid,
                    name=name,
                    is_registered_on_device=True,
                    fingerprint_registered=False,
                )
                logger.info("Synced '%s' → device uid=%d user_id=%s", name, device_uid, cuid)
            except Exception as exc:
                logger.error("Failed to sync user cuid=%s uid=%d: %s", cuid, device_uid, exc)

        # 3. Read all device users + fingerprint status.
        device_users = []
        try:
            device_users = self._device.get_users_with_fingerprint_status()
            logger.info("Device has %d enrolled users", len(device_users))
        except Exception as exc:
            logger.warning("Could not read device users: %s", exc)

        # 3a. Detect newly enrolled fingerprints by comparing device state vs DB.
        #     Flip fp_sync_pending=True so they are PATCHed to the server on the
        #     next flush pass (step 0) or at the end of this cycle if server is up.
        if device_users:
            db_users = {u["biometric_number"]: u for u in db.get_all_users()}
            for du in device_users:
                bnum = du["uid"]
                fp_on_device = bool(du.get("fingerprint_registered", False))
                existing = db_users.get(bnum)
                if existing is not None:
                    was_enrolled = bool(existing["fingerprint_registered"])
                    if fp_on_device and not was_enrolled:
                        # Newly enrolled — mark pending so server is notified
                        db.update_fp_status(
                            biometric_number=bnum,
                            fingerprint_registered=True,
                            fp_sync_pending=True,
                        )
                        logger.info("Fingerprint newly enrolled for uid=%d — queued for server sync", bnum)
                    elif not fp_on_device and was_enrolled:
                        # Fingerprint removed from device
                        db.update_fp_status(
                            biometric_number=bnum,
                            fingerprint_registered=False,
                            fp_sync_pending=False,
                        )
                else:
                    # User exists on device but not in DB (added outside this agent).
                    # Persist without a server CUID — user_id defaults to biometric_number str.
                    db.upsert_user(
                        biometric_number=bnum,
                        user_id=str(bnum),
                        name=du.get("name", "Unknown"),
                        is_registered_on_device=True,
                        fingerprint_registered=fp_on_device,
                    )

        # 3b. Immediately flush any FP enrollments detected in this cycle.
        newly_pending = db.get_fp_pending_users()
        if newly_pending and _server_ok:
            fp_statuses = [
                {
                    "id": u["user_id"],
                    "isRegistered": True,
                    "isFingerPrintRegistered": True,
                }
                for u in newly_pending
            ]
            try:
                self._api.mark_users_registered(fp_statuses)
                db.clear_fp_pending([u["user_id"] for u in newly_pending])
                logger.info("Reported %d new FP enrollment(s) to server", len(newly_pending))
            except Exception as exc:
                logger.warning("Could not report new FP enrollments (will retry): %s", exc)

        # 4. Report isRegistered + isFingerPrintRegistered back to server for the
        #    batch of newly-pushed unregistered users.
        if unregistered:
            fp_by_serial: dict[str, bool] = {
                str(u["uid"]): u["fingerprint_registered"] for u in device_users
            }
            registered_serials: set[str] = {str(u["uid"]) for u in device_users}

            statuses = [
                {
                    "id": user["id"],
                    "isRegistered": str(user["biometricNumber"]) in registered_serials,
                    "isFingerPrintRegistered": fp_by_serial.get(str(user["biometricNumber"]), False),
                }
                for user in unregistered
            ]

            try:
                self._api.mark_users_registered(statuses)
                logger.info("Reported registration status for %d users", len(statuses))
            except Exception as exc:
                logger.warning("Could not PATCH mark-registered: %s", exc)

        # 5. Update dashboard cache from the local DB (always reflects persisted state).
        all_db_users = db.get_all_users()
        with self._lock:
            self._cached_students = [
                {
                    "uid": u["biometric_number"],
                    "user_id": u["user_id"],
                    "name": u["name"],
                    "fingerprint_registered": bool(u["fingerprint_registered"]),
                }
                for u in all_db_users
            ]

        # 6. Cache device info for the dashboard.
        try:
            info = self._device.get_info()
            with self._lock:
                self._cached_device_info = info
        except Exception as exc:
            logger.debug("Could not refresh cached device info: %s", exc)

        # 7. Persist server reachability for the dashboard status cards.
        with self._lock:
            self.server_reachable = _server_ok


