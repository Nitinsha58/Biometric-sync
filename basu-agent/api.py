"""
api.py — HTTP client for all BASU server endpoints.

All requests include X-Api-Key and X-Center-Id headers.
Raises requests.HTTPError on non-2xx responses.
"""

import logging
from typing import Any

import requests

import config

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds per request


class APIClient:
    """Handles all outbound HTTP calls to the BASU AWS server."""

    def __init__(
        self,
        server_url: str = config.SERVER_URL,
        api_key: str = config.API_KEY,
        center_id: str = config.CENTER_ID,
    ):
        self.base_url = server_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-Api-Key": api_key,
                "X-Center-Id": center_id,
                "Content-Type": "application/json",
            }
        )

    def _post(self, path: str, payload: Any) -> dict:
        url = f"{self.base_url}{path}"
        resp = self._session.post(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        logger.info("POST %s → %s", url, resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {}

    def _get(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        resp = self._session.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        logger.info("GET %s → %s", url, resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {}

    def _patch(self, path: str, payload: Any) -> dict:
        url = f"{self.base_url}{path}"
        resp = self._session.patch(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        logger.info("PATCH %s → %s", url, resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {}

    # -----------------------------------------------------------------
    # Endpoint methods
    # -----------------------------------------------------------------

    def get_unregistered_users(self) -> list[dict]:
        """
        GET /attendance-sync/unregistered-users
        Returns: {success, data: {users: [{id, name, biometricNumber}, ...]}}
        biometricNumber is the integer uid to use on the device.
        user_id (string) on the device stores the server CUID (id field).
        """
        result = self._get("/attendance-sync/unregistered-users")
        if isinstance(result, list):
            return result
        # Server wraps response: {data: {users: [...]}}
        return result.get("data", {}).get("users", [])

    def mark_users_registered(self, statuses: list[dict]) -> dict:
        """
        PATCH /attendance-sync/mark-registered
        Payload: {users: [{id, isRegistered, isFingerPrintRegistered}, ...]}
        id is the server CUID stored as user_id on the device.
        """
        return self._patch("/attendance-sync/mark-registered", {"users": statuses})

    def get_pending_commands(self) -> list[dict]:
        """
        GET /attendance-sync/commands
        Returns list of pending commands for this center/device.
        Each item: {id, type, uid, name, status}
        Falls back to an empty list if the endpoint is absent or returns
        an unexpected shape so the dashboard never crashes.
        """
        try:
            result = self._get("/attendance-sync/commands")
        except Exception as exc:
            logger.warning("get_pending_commands failed: %s", exc)
            return []
        if isinstance(result, list):
            return result
        # Tolerate wrapped shapes: {data: [...]} or {data: {commands: [...]}}
        data = result.get("data", result)
        if isinstance(data, list):
            return data
        return data.get("commands", [])

    def post_device_info(self, info: dict) -> dict:
        """
        POST /attendance-sync/device-info
        Payload: device metadata dict returned by ZKDevice.get_info().
        Silently no-ops (returns {}) if the endpoint is unavailable.
        """
        try:
            return self._post("/attendance-sync/device-info", info)
        except Exception as exc:
            logger.warning("post_device_info failed: %s", exc)
            return {}
