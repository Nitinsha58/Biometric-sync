"""
startup.py — Windows startup registry helpers for the BASU Biometric Agent.

Uses HKCU\Software\Microsoft\Windows\CurrentVersion\Run — no admin rights needed.
Works for both PyInstaller frozen builds and plain dev-mode Python scripts.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_KEY_PATH   = r"Software\Microsoft\Windows\CurrentVersion\Run"
_ENTRY_NAME = "BASU_Biometric_Agent"


def _launch_command() -> str:
    """
    Build the registry command that starts the agent.

    Frozen .exe  → absolute path to the executable wrapped in quotes.
    Dev Python   → pythonw.exe  +  absolute path to main.py  (no console window).
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    script  = Path(__file__).with_name("main.py").resolve()
    return f'"{pythonw}" "{script}"'


def is_registered() -> bool:
    """Return True if the startup registry entry already exists."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY_PATH) as key:
            winreg.QueryValueEx(key, _ENTRY_NAME)
        return True
    except OSError:
        return False


def register() -> None:
    """Add / update the startup registry entry (idempotent)."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        cmd = _launch_command()
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _ENTRY_NAME, 0, winreg.REG_SZ, cmd)
        logger.info("Registered Windows startup: %s", cmd)
    except Exception as exc:
        logger.warning("Could not register startup: %s", exc)


def unregister() -> None:
    """Remove the startup registry entry (silent no-op if not present)."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _ENTRY_NAME)
        logger.info("Unregistered Windows startup")
    except OSError:
        pass
    except Exception as exc:
        logger.warning("Could not unregister startup: %s", exc)
