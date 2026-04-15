"""
config.py — Loads config.json and exposes typed constants.

When running as a frozen PyInstaller bundle, config.json and agent.log are
stored in %APPDATA%\\BASU_Biometric_Agent\\ so the operator can edit settings
without touching the install directory.  On first run the bundled default
config.json is copied there automatically.

In dev mode both files live alongside this script (basu-agent/).
"""

import json
import os
import sys
from pathlib import Path


# ------------------------------------------------------------------
# Paths — importable by other modules
# ------------------------------------------------------------------

def _get_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        d = appdata / "BASU_Biometric_Agent"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).parent


DATA_DIR    = _get_data_dir()
CONFIG_PATH = DATA_DIR / "config.json"
LOG_PATH    = DATA_DIR / "agent.log"


def _seed_config_if_missing() -> None:
    """On first frozen run, copy the bundled default config.json to AppData."""
    if CONFIG_PATH.exists():
        return
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "config.json"  # type: ignore[attr-defined]
        if bundled.exists():
            CONFIG_PATH.write_bytes(bundled.read_bytes())


_seed_config_if_missing()


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json not found at {CONFIG_PATH}. "
            "Edit the config via the dashboard Settings page."
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_cfg = _load_config()

CENTER_ID: str     = _cfg["center_id"]
DEVICE_IP: str     = _cfg["device_ip"]
DEVICE_PORT: int   = int(_cfg.get("device_port", 4370))
API_KEY: str       = _cfg["api_key"]
SERVER_URL: str    = _cfg["server_url"].rstrip("/")
SYNC_INTERVAL: int = int(_cfg.get("sync_interval_seconds", 30))


def reload() -> None:
    """Re-read config.json and update all module-level constants (hot reload).

    Called by SyncWorker.reload_config() after the dashboard saves new settings
    so connectivity changes take effect immediately without restarting the agent.
    """
    global CENTER_ID, DEVICE_IP, DEVICE_PORT, API_KEY, SERVER_URL, SYNC_INTERVAL, _cfg
    _cfg          = _load_config()
    CENTER_ID     = _cfg["center_id"]
    DEVICE_IP     = _cfg["device_ip"]
    DEVICE_PORT   = int(_cfg.get("device_port", 4370))
    API_KEY       = _cfg["api_key"]
    SERVER_URL    = _cfg["server_url"].rstrip("/")
    SYNC_INTERVAL = int(_cfg.get("sync_interval_seconds", 30))
