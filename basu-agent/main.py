"""
main.py — Entry point for the BASU Biometric Agent.

- Creates a system tray icon (PyQt6 QSystemTrayIcon)
- Starts the background SyncWorker thread on launch
- Posts device info to the server on startup
- Registers the app in Windows startup (startup folder, Windows only)
- Right-click tray menu: Open Dashboard | Sync Now | Quit
"""

import logging
import sys
from pathlib import Path

# Allow running directly from basu-agent/ or repo root
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PyQt6.QtCore import QTimer

import config
import startup
from api import APIClient
from device import ZKDevice
from worker import SyncWorker
from zk.exception import ZKNetworkError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_tray_icon(online: bool = True) -> QIcon:
    """Create a simple coloured-circle icon (green=online, grey=unknown)."""
    colour = "#4CAF50" if online else "#9E9E9E"
    px = QPixmap(22, 22)
    px.fill(QColor(0, 0, 0, 0))
    from PyQt6.QtGui import QPainter, QBrush
    from PyQt6.QtCore import Qt
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(colour)))
    painter.setPen(QColor(colour))
    painter.drawEllipse(2, 2, 18, 18)
    painter.end()
    return QIcon(px)


def _post_device_info_on_startup():
    """Read device info and POST to server. Errors are logged, not raised."""
    try:
        device = ZKDevice()
        info = device.get_info()
        api = APIClient()
        api.post_device_info(info)
        logger.info("Startup device info posted: serial=%s", info.get("serial_number"))
    except (ZKNetworkError, OSError) as exc:
        logger.warning("Could not read device on startup (will retry on next sync): %s", exc)
    except Exception as exc:
        logger.warning("Startup device-info POST failed: %s", exc)


# ------------------------------------------------------------------
# Main application
# ------------------------------------------------------------------

class BASUAgent:
    def __init__(self, app: QApplication):
        self.app = app
        self.worker = SyncWorker()
        self._dashboard = None  # lazily created

        # Tray icon
        self.tray = QSystemTrayIcon(_make_tray_icon(online=False), parent=None)
        self.tray.setToolTip("BASU Biometric Agent")
        self._build_tray_menu()
        self.tray.show()

        # Update tray icon colour based on worker status every 10 s
        self._icon_timer = QTimer()
        self._icon_timer.timeout.connect(self._refresh_tray_icon)
        self._icon_timer.start(10_000)

    def _build_tray_menu(self):
        menu = QMenu()

        open_action = menu.addAction("Open Dashboard")
        open_action.triggered.connect(self._open_dashboard)

        sync_action = menu.addAction("Sync Now")
        sync_action.triggered.connect(self._sync_now)

        menu.addSeparator()

        self._startup_action = menu.addAction(
            "✓  Run on Startup" if startup.is_registered() else "Run on Startup"
        )
        self._startup_action.setCheckable(True)
        self._startup_action.setChecked(startup.is_registered())
        self._startup_action.triggered.connect(self._toggle_startup)

        menu.addSeparator()

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)

        self.tray.setContextMenu(menu)

    def _refresh_tray_icon(self):
        self.tray.setIcon(_make_tray_icon(online=self.worker.device_online))

    def _open_dashboard(self):
        from dashboard import DashboardWindow
        if self._dashboard is None or not self._dashboard.isVisible():
            self._dashboard = DashboardWindow(worker=self.worker)
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()

    def _sync_now(self):
        logger.info("Manual sync triggered from tray")
        self.worker.run_once()
        self.tray.showMessage(
            "BASU Agent", "Sync started…", QSystemTrayIcon.MessageIcon.Information, 2000
        )

    def _toggle_startup(self):
        if startup.is_registered():
            startup.unregister()
            self.tray.showMessage(
                "BASU Agent", "Removed from Windows startup.",
                QSystemTrayIcon.MessageIcon.Information, 2000,
            )
        else:
            startup.register()
            self.tray.showMessage(
                "BASU Agent", "Agent will run automatically on Windows login.",
                QSystemTrayIcon.MessageIcon.Information, 2000,
            )
        # Rebuild menu so the checkmark and label stay in sync
        self._build_tray_menu()

    def _quit(self):
        logger.info("Quit requested — stopping worker")
        self.worker.stop()
        self.tray.hide()
        self.app.quit()

    def start(self):
        # Auto-register Windows startup on first launch (if not already done)
        if sys.platform == "win32" and not startup.is_registered():
            startup.register()
        _post_device_info_on_startup()
        self.worker.start()
        logger.info("BASU Biometric Agent running (center=%s)", config.CENTER_ID)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep alive when dashboard closes

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("System tray not available on this platform.")
        sys.exit(1)

    agent = BASUAgent(app)
    agent.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
