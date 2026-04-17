"""
dashboard.py — Modern management dashboard for the BASU Biometric Agent.

5 navigable pages:
  Overview    — stat cards, device info, recent log
  Students    — user table with search, add, individual & bulk delete
  Attendance  — device attendance records with filter, individual & bulk clear
  Activity Log — live terminal-style log viewer
  Settings    — edit config.json
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSpinBox, QStackedWidget,
    QStatusBar, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

import config
import db
from worker import SyncWorker

logger = logging.getLogger(__name__)

# In frozen builds these resolve to %APPDATA%\BASU_Biometric_Agent\
LOG_PATH    = config.LOG_PATH
CONFIG_PATH = config.CONFIG_PATH

# ── Colour palette (GitHub-dark inspired) ─────────────────────────
BG_MAIN    = "#0d1117"
BG_CARD    = "#161b22"
BG_SIDEBAR = "#010409"
BG_INPUT   = "#21262d"
ACCENT     = "#7c3aed"
ACCENT_DIM = "#4c1d95"
SUCCESS    = "#3fb950"
ERROR      = "#f85149"
WARNING    = "#d29922"
INFO       = "#58a6ff"
TEXT_PRI   = "#e6edf3"
TEXT_SEC   = "#8b949e"
BORDER     = "#30363d"
ROW_ALT    = "#1c2128"

# ── Global stylesheet ─────────────────────────────────────────────
STYLESHEET = f"""
QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT_PRI};
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
}}
QMainWindow {{ background-color: {BG_MAIN}; }}

#Sidebar {{ background-color: {BG_SIDEBAR}; border-right: 1px solid {BORDER}; }}
#TopBar  {{ background-color: {BG_SIDEBAR}; border-bottom: 1px solid {BORDER}; }}

QPushButton#nav_btn {{
    background: transparent; border: none; border-radius: 6px;
    color: {TEXT_SEC}; font-size: 13px; padding: 10px 14px; text-align: left;
}}
QPushButton#nav_btn:hover {{ background-color: {BG_INPUT}; color: {TEXT_PRI}; }}
QPushButton#nav_btn[active="true"] {{
    background-color: {ACCENT}; color: #ffffff; font-weight: bold;
}}

QFrame#Card {{
    background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px;
}}

QTableWidget {{
    background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    gridline-color: {BORDER}; alternate-background-color: {ROW_ALT};
    selection-background-color: {ACCENT_DIM}; outline: none;
}}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QHeaderView::section {{
    background-color: {BG_MAIN}; color: {TEXT_SEC}; font-size: 11px;
    font-weight: bold; padding: 6px 10px; border: none;
    border-bottom: 1px solid {BORDER};
}}
QTableCornerButton::section {{ background-color: {BG_MAIN}; border: none; }}

QLineEdit, QSpinBox, QComboBox {{
    background-color: {BG_INPUT}; border: 1px solid {BORDER};
    border-radius: 6px; color: {TEXT_PRI}; padding: 6px 10px; font-size: 13px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_INPUT}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; color: {TEXT_PRI};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {BG_INPUT}; border: none; width: 18px;
}}

QPushButton {{
    background-color: {BG_INPUT}; border: 1px solid {BORDER};
    border-radius: 6px; color: {TEXT_PRI}; padding: 7px 16px; font-size: 13px;
}}
QPushButton:hover {{ background-color: #2d333b; border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: {ACCENT}; }}
QPushButton#accent_btn {{
    background-color: {ACCENT}; border: none; color: #ffffff; font-weight: bold;
}}
QPushButton#accent_btn:hover {{ background-color: #6d28d9; }}
QPushButton#danger_btn {{
    background-color: transparent; border: 1px solid {BORDER};
    color: {ERROR}; font-size: 12px; padding: 4px 10px;
}}
QPushButton#danger_btn:hover {{
    background-color: rgba(248,81,73,0.12); border-color: {ERROR};
}}
QPushButton#sync_btn {{
    background-color: {ACCENT}; border: none; color: #ffffff;
    font-weight: bold; padding: 7px 18px; border-radius: 6px;
}}
QPushButton#sync_btn:hover {{ background-color: #6d28d9; }}

QTextEdit#LogView {{
    background-color: #0a0e14; color: {SUCCESS};
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px; border: 1px solid {BORDER}; border-radius: 6px;
}}

QScrollBar:vertical {{
    background: {BG_CARD}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_CARD}; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 4px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QStatusBar {{
    background-color: {BG_SIDEBAR}; border-top: 1px solid {BORDER};
    color: {TEXT_SEC}; font-size: 12px; padding: 3px 8px;
}}
QStatusBar::item {{ border: none; }}
QDialog {{ background-color: {BG_CARD}; }}
QMessageBox {{ background-color: {BG_CARD}; }}
"""

# ─────────────────────────────────────────────────────────────────
#  Tiny UI helpers
# ─────────────────────────────────────────────────────────────────

def _badge(text: str, bg: str, fg: str = "#ffffff") -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedHeight(22)
    lbl.setStyleSheet(
        f"background-color:{bg}; color:{fg}; border-radius:11px;"
        f" padding:0 10px; font-size:11px; font-weight:bold;"
    )
    return lbl


def _cell_widget(w: QWidget) -> QWidget:
    container = QWidget()
    container.setStyleSheet("background:transparent;")
    lay = QHBoxLayout(container)
    lay.setContentsMargins(6, 2, 6, 2)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(w)
    return container


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{TEXT_SEC}; font-size:11px; font-weight:bold;"
        f" letter-spacing:1px; background:transparent; border:none; padding:0;"
    )
    return lbl


def _h_line() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background:{BORDER}; border:none; max-height:1px;")
    return line


def _dim_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{TEXT_SEC}; background:transparent; border:none;")
    return lbl


# ─────────────────────────────────────────────────────────────────
#  Generic background data loader
# ─────────────────────────────────────────────────────────────────

class DataLoader(QThread):
    result = pyqtSignal(object)
    error  = pyqtSignal(str)

    def __init__(self, fn: Callable, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self.result.emit(self._fn())
        except Exception as exc:
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────
#  StatCard
# ─────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, title: str, value: str = "—", accent: str = ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedSize(158, 90)
        self._accent = accent

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(4)

        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"color:{TEXT_PRI}; font-size:28px; font-weight:bold; background:transparent; border:none;"
        )
        self._ttl = QLabel(title)
        self._ttl.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:11px; background:transparent; border:none;"
        )
        lay.addWidget(self._val)
        lay.addWidget(self._ttl)

    def set_value(self, v: str):
        self._val.setText(v)

    def set_accent(self, color: str):
        self._accent = color
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(self._accent))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 10, 4, self.height() - 20, 2, 2)
        p.end()


# ═════════════════════════════════════════════════════════════════
#  PAGE 1 — Overview
# ═════════════════════════════════════════════════════════════════

class OverviewPage(QWidget):
    def __init__(self, worker: SyncWorker, parent=None):
        super().__init__(parent)
        self._worker = worker

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # Stat cards
        row = QHBoxLayout()
        row.setSpacing(12)
        self._c_users  = StatCard("Device Users",  "—", ACCENT)
        self._c_fp     = StatCard("Fingerprinted", "—", SUCCESS)
        self._c_nofp   = StatCard("Not Enrolled",  "—", WARNING)
        self._c_server = StatCard("Server",        "—", TEXT_SEC)
        for c in [self._c_users, self._c_fp, self._c_nofp, self._c_server]:
            row.addWidget(c)
        row.addStretch()
        root.addLayout(row)

        # Lower split
        lower = QHBoxLayout()
        lower.setSpacing(16)
        lower.addWidget(self._build_device_card(), stretch=1)
        lower.addWidget(self._build_log_card(),    stretch=1)
        root.addLayout(lower, stretch=1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

    # ── Device info card ──────────────────────────────────────────

    def _build_device_card(self) -> QFrame:
        f = QFrame(); f.setObjectName("Card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_section_label("Device Information"))
        lay.addWidget(_h_line())

        self._drows: dict[str, QLabel] = {}
        for key, label in [
            ("serial_number",    "Serial Number"),
            ("device_name",      "Device Name"),
            ("firmware_version", "Firmware"),
            ("platform",         "Platform"),
            ("device_time",      "Device Time"),
        ]:
            row = QHBoxLayout()
            k = _dim_label(label); k.setFixedWidth(130)
            v = QLabel("—"); v.setStyleSheet(f"color:{TEXT_PRI}; background:transparent; border:none;")
            v.setWordWrap(True)
            self._drows[key] = v
            row.addWidget(k); row.addWidget(v, stretch=1)
            lay.addLayout(row)

        # Sync timing rows
        for attr, label in [("_last_sync_lbl", "Last Sync"), ("_next_sync_lbl", "Next Sync In")]:
            row = QHBoxLayout()
            k = _dim_label(label); k.setFixedWidth(130)
            v = QLabel("—"); v.setStyleSheet(f"color:{TEXT_PRI}; background:transparent; border:none;")
            setattr(self, attr, v)
            row.addWidget(k); row.addWidget(v, stretch=1)
            lay.addLayout(row)

        self._drift_lbl = QLabel("")
        self._drift_lbl.setStyleSheet("background:transparent; border:none;")
        self._drift_lbl.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self._drift_lbl)
        lay.addStretch()
        return f

    # ── Recent log card ───────────────────────────────────────────

    def _build_log_card(self) -> QFrame:
        f = QFrame(); f.setObjectName("Card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(_section_label("Recent Activity"))
        lay.addWidget(_h_line())

        self._log_box = QTextEdit()
        self._log_box.setObjectName("LogView")
        self._log_box.setReadOnly(True)
        self._log_box.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self._log_box, stretch=1)

        t = QTimer(self); t.timeout.connect(self._refresh_log); t.start(8_000)
        return f

    def _refresh_log(self):
        try:
            lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            self._log_box.setPlainText("\n".join(lines[-25:]))
            cur = self._log_box.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self._log_box.setTextCursor(cur)
        except FileNotFoundError:
            self._log_box.setPlainText("No log yet.")

    def refresh(self):
        with self._worker._lock:
            info      = dict(self._worker._cached_device_info)
            last_sync = self._worker.last_sync_time
            server_ok = self._worker.server_reachable

        stats = db.count_stats()
        self._c_users.set_value(str(stats["total"]))
        self._c_fp.set_value(str(stats["fingerprinted"]))
        self._c_nofp.set_value(str(stats["not_enrolled"]))

        # Server status card
        self._c_server.set_value("Online" if server_ok else "Offline")
        self._c_server.set_accent(SUCCESS if server_ok else ERROR)

        # Sync timing labels
        self._last_sync_lbl.setText(
            last_sync.strftime("%H:%M:%S") if last_sync else "—"
        )
        nsi = self._worker.next_sync_in
        self._next_sync_lbl.setText(f"{nsi}s" if nsi > 0 else "—")

        for key, lbl in self._drows.items():
            lbl.setText(str(info.get(key, "—")))

        dev_time_str = info.get("device_time", "")
        if dev_time_str:
            try:
                drift = abs((datetime.now() - datetime.fromisoformat(dev_time_str)).total_seconds())
                if drift > 60:
                    self._drift_lbl.setText(
                        f'<span style="color:{WARNING}">⚠ Clock drift: {int(drift)}s</span>'
                    )
                else:
                    self._drift_lbl.setText(
                        f'<span style="color:{SUCCESS}">✓ Clock in sync</span>'
                    )
            except ValueError:
                pass

        self._refresh_log()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()


# ═════════════════════════════════════════════════════════════════
#  PAGE 2 — Students
# ═════════════════════════════════════════════════════════════════

class StudentsPage(QWidget):
    def __init__(self, worker: SyncWorker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._loader: Optional[DataLoader] = None
        self._all: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Toolbar
        tb = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search by name or UID…")
        self._search.setFixedHeight(36); self._search.setMaximumWidth(320)
        self._search.textChanged.connect(self._populate)

        self._stat_lbl = QLabel("")
        self._stat_lbl.setStyleSheet(f"color:{TEXT_SEC}; background:transparent; border:none;")

        self._last_sync_lbl = QLabel("")
        self._last_sync_lbl.setStyleSheet(f"color:{TEXT_SEC}; font-size:11px; background:transparent; border:none;")

        self._btn_ref = QPushButton("🔄  Refresh from Device")
        self._btn_ref.setFixedHeight(36); self._btn_ref.clicked.connect(self._load)

        self._btn_add = QPushButton("＋  Add Student")
        self._btn_add.setObjectName("accent_btn"); self._btn_add.setFixedHeight(36)
        self._btn_add.clicked.connect(self._on_add)

        self._btn_del_sel = QPushButton("🗑  Delete Selected")
        self._btn_del_sel.setObjectName("danger_btn"); self._btn_del_sel.setFixedHeight(36)
        self._btn_del_sel.clicked.connect(self._on_delete_selected)

        tb.addWidget(self._search); tb.addWidget(self._stat_lbl); tb.addWidget(self._last_sync_lbl)
        tb.addStretch()
        tb.addWidget(self._btn_ref); tb.addWidget(self._btn_del_sel); tb.addWidget(self._btn_add)
        root.addLayout(tb)

        self._loading_lbl = QLabel("Refreshing from device…")
        self._loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_lbl.setStyleSheet(
            f"color:{TEXT_SEC}; font-size:14px; background:transparent; border:none;"
        )
        self._loading_lbl.hide()
        root.addWidget(self._loading_lbl)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["UID", "Name", "User ID", "Fingerprint", "Action"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in [0, 2, 3, 4]:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        root.addWidget(self._table, stretch=1)

    def _populate(self):
        q = self._search.text().lower()
        visible = [s for s in self._all if not q or q in s["name"].lower() or q in str(s["uid"])]

        fp = sum(1 for s in self._all if s.get("fingerprint_registered"))
        self._stat_lbl.setText(
            f"{len(self._all)} students · {fp} fingerprinted · {len(self._all)-fp} not enrolled"
        )

        self._table.setRowCount(0)
        for ri, s in enumerate(visible):
            self._table.insertRow(ri)
            self._table.setRowHeight(ri, 44)

            uid_i  = QTableWidgetItem(str(s["uid"]))
            uid_i.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            uid_s_i = QTableWidgetItem(str(s.get("user_id", s["uid"])))
            uid_s_i.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            fp_ok = s.get("fingerprint_registered", False)
            fp_b  = _badge("✓  Enrolled", SUCCESS) if fp_ok else _badge("Not enrolled", BG_INPUT, TEXT_SEC)

            del_btn = QPushButton("Delete")
            del_btn.setObjectName("danger_btn"); del_btn.setFixedHeight(28)
            del_btn.clicked.connect(
                lambda _, u=s["uid"], n=s["name"]: self._on_delete(u, n)
            )

            self._table.setItem(ri, 0, uid_i)
            self._table.setItem(ri, 1, QTableWidgetItem(s["name"]))
            self._table.setItem(ri, 2, uid_s_i)
            self._table.setCellWidget(ri, 3, _cell_widget(fp_b))
            self._table.setCellWidget(ri, 4, _cell_widget(del_btn))

    def _load(self):
        """Trigger a full device read (slow path). Normal display uses _load_from_db()."""
        from device import ZKDevice
        self._btn_ref.setEnabled(False)
        self._btn_ref.setText("Refreshing…")
        self._loading_lbl.show()
        self._loader = DataLoader(ZKDevice().get_users_with_fingerprint_status, self)
        self._loader.result.connect(self._on_loaded)
        self._loader.error.connect(self._on_err)
        self._loader.start()

    def _on_loaded(self, students: list):
        """Called when a full device read finishes. Upserts rows into the DB, then reloads from DB."""
        self._btn_ref.setEnabled(True)
        self._btn_ref.setText("🔄  Refresh from Device")
        self._loading_lbl.hide()
        # Persist the fresh device snapshot to the local DB
        for s in students:
            # User may not have a server CUID if added locally; default to biometric_number str
            existing = next(
                (u for u in db.get_all_users() if u["biometric_number"] == s["uid"]), None
            )
            db.upsert_user(
                biometric_number=s["uid"],
                user_id=existing["user_id"] if existing else str(s["uid"]),
                name=s["name"],
                is_registered_on_device=True,
                fingerprint_registered=bool(s.get("fingerprint_registered", False)),
            )
        self._load_from_db()
        with self._worker._lock:
            self._worker._cached_students = list(self._all)

    def _load_from_db(self):
        """Populate the table instantly from the local SQLite DB (no device round-trip)."""
        users = db.get_all_users()
        self._all = [
            {
                "uid": u["biometric_number"],
                "user_id": u["user_id"],
                "name": u["name"],
                "fingerprint_registered": bool(u["fingerprint_registered"]),
            }
            for u in users
        ]
        last_sync = self._worker.last_sync_time
        if last_sync:
            delta = int((datetime.now() - last_sync).total_seconds())
            if delta < 60:
                self._last_sync_lbl.setText(f"synced {delta}s ago")
            else:
                self._last_sync_lbl.setText(f"synced {delta // 60}m ago")
        else:
            self._last_sync_lbl.setText("not synced yet")
        self._populate()

    def _on_err(self, err: str):
        self._btn_ref.setEnabled(True)
        self._btn_ref.setText("🔄  Refresh from Device")
        self._loading_lbl.setText(f"Device error: {err}")
        self._loading_lbl.show()
        QTimer.singleShot(5000, self._loading_lbl.hide)

    def _on_add(self):
        dlg = _AddStudentDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        uid, name = dlg.result_uid, dlg.result_name
        self._btn_add.setEnabled(False)
        self._btn_add.setText("Adding…")

        def _do_add():
            from device import ZKDevice
            ZKDevice().set_user(uid=uid, name=name, user_id=str(uid))
            db.upsert_user(
                biometric_number=uid,
                user_id=str(uid),
                name=name,
                is_registered_on_device=True,
                fingerprint_registered=False,
            )

        def _on_add_done(_):
            self._btn_add.setEnabled(True)
            self._btn_add.setText("＋  Add Student")
            self._load_from_db()

        def _on_add_err(e: str):
            self._btn_add.setEnabled(True)
            self._btn_add.setText("＋  Add Student")
            QMessageBox.critical(self, "Error", f"Could not add student:\n{e}")

        loader = DataLoader(_do_add, self)
        loader.result.connect(_on_add_done)
        loader.error.connect(_on_add_err)
        loader.start()

    def _on_delete(self, uid: int, name: str):
        if QMessageBox.question(
            self, "Delete Student",
            f"Remove <b>{name}</b> (UID {uid}) from the device?<br>"
            f"<small>This does not affect the portal.</small>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return

        def _do_delete():
            from device import ZKDevice
            ZKDevice().delete_user(uid=uid)
            db.delete_user(uid)

        loader = DataLoader(_do_delete, self)
        loader.result.connect(lambda _: self._load_from_db())
        loader.error.connect(lambda e: QMessageBox.critical(self, "Error", str(e)))
        loader.start()

    def _on_delete_selected(self):
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Select one or more students to delete.")
            return
        uids, names = [], []
        for index in selected_rows:
            row = index.row()
            uid_item  = self._table.item(row, 0)
            name_item = self._table.item(row, 1)
            if uid_item:
                try:
                    uids.append(int(uid_item.text()))
                    names.append(name_item.text() if name_item else uid_item.text())
                except ValueError:
                    pass
        if not uids:
            return

        # Use a fixed-size dialog so the list can't push the window off-screen
        dlg = QDialog(self)
        dlg.setWindowTitle("Delete Students")
        dlg.setFixedWidth(420)
        dlg.setMaximumHeight(480)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        lbl = QLabel(f"Remove <b>{len(uids)}</b> student(s) from the device?<br>"
                     f"<small>This does not affect the portal.</small>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        summary_box = QTextEdit()
        summary_box.setReadOnly(True)
        summary_box.setFixedHeight(160)
        summary_box.setObjectName("LogView")
        summary_box.setPlainText("\n".join(f"  • {n}  (UID {u})" for u, n in zip(uids, names)))
        lay.addWidget(summary_box)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok = QPushButton("Delete")
        btn_ok.setObjectName("danger_btn")
        btn_ok.setFixedHeight(34)
        btn_ok.clicked.connect(dlg.accept)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        lay.addLayout(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._btn_del_sel.setEnabled(False)
        self._btn_del_sel.setText("Deleting…")

        def _bulk_delete():
            from device import ZKDevice
            dev = ZKDevice()
            for uid in uids:
                dev.delete_user(uid=uid)
                db.delete_user(uid)

        def _on_bulk_done(_):
            self._btn_del_sel.setEnabled(True)
            self._btn_del_sel.setText("🗑  Delete Selected")
            self._load_from_db()

        def _on_bulk_err(e: str):
            self._btn_del_sel.setEnabled(True)
            self._btn_del_sel.setText("🗑  Delete Selected")
            QMessageBox.critical(self, "Error", str(e))

        loader = DataLoader(_bulk_delete, self)
        loader.result.connect(_on_bulk_done)
        loader.error.connect(_on_bulk_err)
        loader.start()

    def showEvent(self, event):
        super().showEvent(event)
        # Load instantly from local DB — no device round-trip needed on every open
        self._load_from_db()


# ═════════════════════════════════════════════════════════════════
#  PAGE 3 — Attendance
# ═════════════════════════════════════════════════════════════════

class AttendancePage(QWidget):
    def __init__(self, worker: SyncWorker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._loader: Optional[DataLoader] = None
        self._all: list[dict] = []
        self._uid_name: dict[str, str] = {}
        self._first = True

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        tb = QHBoxLayout()
        self._stat_lbl = QLabel("—")
        self._stat_lbl.setStyleSheet(f"color:{TEXT_SEC}; background:transparent; border:none;")

        self._filter = QComboBox()
        self._filter.addItems(["All Records", "Today", "Last 7 Days"])
        self._filter.setFixedHeight(36); self._filter.setFixedWidth(160)
        self._filter.currentIndexChanged.connect(self._apply_filter)

        btn_ref = QPushButton("🔄  Refresh from Device")
        btn_ref.setFixedHeight(36); btn_ref.clicked.connect(self._load)

        btn_clear_all = QPushButton("🗑  Clear All Records")
        btn_clear_all.setObjectName("danger_btn"); btn_clear_all.setFixedHeight(36)
        btn_clear_all.clicked.connect(self._on_clear_all)

        tb.addWidget(self._stat_lbl); tb.addStretch()
        tb.addWidget(self._filter); tb.addWidget(btn_ref); tb.addWidget(btn_clear_all)
        root.addLayout(tb)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["User ID", "Name", "Date", "Time", "Type", "Action"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in [0, 2, 3, 4, 5]:
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        root.addWidget(self._table, stretch=1)

    def _load(self):
        from device import ZKDevice
        self._stat_lbl.setText("Loading…")
        self._loader = DataLoader(ZKDevice().get_attendance, self)
        self._loader.result.connect(self._on_loaded)
        self._loader.error.connect(lambda e: self._stat_lbl.setText(f"Error: {e}"))
        self._loader.start()

    def _on_loaded(self, records: list):
        with self._worker._lock:
            cached = list(self._worker._cached_students)
        self._uid_name = {str(s["uid"]): s["name"] for s in cached}
        self._all = sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)
        self._apply_filter()

    def _apply_filter(self):
        idx = self._filter.currentIndex()
        now = datetime.now()
        rows = []
        for r in self._all:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except (ValueError, KeyError):
                ts = None
            if idx == 1 and ts and ts.date() != now.date():
                continue
            if idx == 2 and ts and (now - ts).days > 7:
                continue
            rows.append((r, ts))

        self._stat_lbl.setText(f"{len(rows)} records")
        self._table.setRowCount(0)
        for ri, (r, ts) in enumerate(rows):
            self._table.insertRow(ri)
            self._table.setRowHeight(ri, 40)
            uid_str = str(r.get("user_id", "—"))
            self._table.setItem(ri, 0, QTableWidgetItem(uid_str))
            self._table.setItem(ri, 1, QTableWidgetItem(self._uid_name.get(uid_str, "—")))
            self._table.setItem(ri, 2, QTableWidgetItem(ts.strftime("%d %b %Y") if ts else "—"))
            self._table.setItem(ri, 3, QTableWidgetItem(ts.strftime("%H:%M:%S") if ts else "—"))
            badge = _badge("Check In", INFO) if r.get("punch", 0) == 0 else _badge("Check Out", BG_INPUT, TEXT_SEC)
            self._table.setCellWidget(ri, 4, _cell_widget(badge))
            del_btn = QPushButton("Delete")
            del_btn.setObjectName("danger_btn"); del_btn.setFixedHeight(28)
            del_btn.clicked.connect(
                lambda _, u=uid_str, dt=(ts.strftime("%d %b %Y %H:%M:%S") if ts else "?"): self._on_delete_record(u, dt)
            )
            self._table.setCellWidget(ri, 5, _cell_widget(del_btn))

    def _on_delete_record(self, uid_str: str, datetime_str: str):
        name = self._uid_name.get(uid_str, f"UID {uid_str}")
        if QMessageBox.question(
            self, "Delete Attendance Record",
            f"Delete the record for <b>{name}</b> at {datetime_str}?<br><br>"
            f"<small><b>Note:</b> The device does not support deleting individual records. "
            f"This will clear <b>all</b> attendance data from the device.</small>",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._on_clear_all(confirmed=True)

    def _on_clear_all(self, confirmed: bool = False):
        if not confirmed:
            if QMessageBox.question(
                self, "Clear All Attendance",
                "Remove <b>all</b> attendance records from the device?<br>"
                "<small>This cannot be undone.</small>",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            ) != QMessageBox.StandardButton.Yes:
                return
        from device import ZKDevice
        loader = DataLoader(ZKDevice().clear_attendance, self)
        loader.result.connect(lambda _: self._load())
        loader.error.connect(lambda e: QMessageBox.critical(self, "Error", str(e)))
        loader.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self._first:
            self._first = False
            self._load()


# ═════════════════════════════════════════════════════════════════
#  PAGE 4 — Activity Log
# ═════════════════════════════════════════════════════════════════

class LogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_scroll = True

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        tb = QHBoxLayout()
        self._as_btn = QPushButton("Auto-scroll: ON")
        self._as_btn.setCheckable(True); self._as_btn.setChecked(True)
        self._as_btn.setFixedHeight(34); self._as_btn.clicked.connect(self._toggle_as)

        btn_clear = QPushButton("Clear Display")
        btn_clear.setFixedHeight(34); btn_clear.clicked.connect(lambda: self._text.clear())

        path_lbl = QLabel(str(LOG_PATH))
        path_lbl.setStyleSheet(f"color:{TEXT_SEC}; font-size:11px; background:transparent; border:none;")

        tb.addWidget(self._as_btn); tb.addWidget(btn_clear); tb.addStretch(); tb.addWidget(path_lbl)
        root.addLayout(tb)

        self._text = QTextEdit()
        self._text.setObjectName("LogView"); self._text.setReadOnly(True)
        self._text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self._text, stretch=1)

        t = QTimer(self); t.timeout.connect(self._refresh); t.start(3_000)

    def _refresh(self):
        try:
            lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            self._text.setPlainText("\n".join(lines[-1000:]))
            if self._auto_scroll:
                cur = self._text.textCursor()
                cur.movePosition(QTextCursor.MoveOperation.End)
                self._text.setTextCursor(cur)
        except FileNotFoundError:
            self._text.setPlainText("No log file yet.")

    def _toggle_as(self, checked: bool):
        self._auto_scroll = checked
        self._as_btn.setText(f"Auto-scroll: {'ON' if checked else 'OFF'}")

    def showEvent(self, event):
        super().showEvent(event); self._refresh()


# ═════════════════════════════════════════════════════════════════
#  PAGE 6 — Settings
# ═════════════════════════════════════════════════════════════════

class SettingsPage(QWidget):
    def __init__(self, worker=None, parent=None):
        super().__init__(parent)
        self._worker = worker

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        card = QFrame(); card.setObjectName("Card"); card.setMaximumWidth(600)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 20, 24, 24); lay.setSpacing(16)
        lay.addWidget(_section_label("Agent Configuration")); lay.addWidget(_h_line())

        form = QFormLayout()
        form.setSpacing(12); form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._f_center = QLineEdit()
        self._f_ip     = QLineEdit()
        self._f_port   = QSpinBox(); self._f_port.setRange(1, 65535)
        self._f_url    = QLineEdit()
        self._f_key    = QLineEdit(); self._f_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._f_int    = QSpinBox();  self._f_int.setRange(10, 3600); self._f_int.setSuffix(" seconds")

        eye = QPushButton("Show"); eye.setFixedWidth(60)
        eye.clicked.connect(lambda: (
            self._f_key.setEchoMode(
                QLineEdit.EchoMode.Normal
                if self._f_key.echoMode() == QLineEdit.EchoMode.Password
                else QLineEdit.EchoMode.Password
            ),
            eye.setText("Hide" if self._f_key.echoMode() == QLineEdit.EchoMode.Normal else "Show"),
        ))
        key_row = QWidget(); key_row.setStyleSheet("background:transparent;")
        kr_lay = QHBoxLayout(key_row); kr_lay.setContentsMargins(0,0,0,0)
        kr_lay.addWidget(self._f_key); kr_lay.addWidget(eye)

        for label, widget in [
            ("Center ID",      self._f_center),
            ("Device IP",      self._f_ip),
            ("Device Port",    self._f_port),
            ("Server URL",     self._f_url),
            ("API Key",        key_row),
            ("Sync Interval",  self._f_int),
        ]:
            lbl = _dim_label(label)
            form.addRow(lbl, widget)
        lay.addLayout(form)

        # ── Test connection buttons ────────────────────────────────
        lay.addWidget(_h_line())
        test_row = QHBoxLayout()
        test_row.setSpacing(10)
        btn_test_dev = QPushButton("🔌  Test Device Connection")
        btn_test_dev.setFixedHeight(36); btn_test_dev.clicked.connect(self._test_device)
        btn_test_srv = QPushButton("🌐  Test Server Connection")
        btn_test_srv.setFixedHeight(36); btn_test_srv.clicked.connect(self._test_server)
        test_row.addWidget(btn_test_dev); test_row.addWidget(btn_test_srv); test_row.addStretch()
        lay.addLayout(test_row)

        # ── Save & Apply button ────────────────────────────────────
        save_btn = QPushButton("💾  Save & Apply")
        save_btn.setObjectName("accent_btn"); save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save)
        lay.addWidget(save_btn)

        note = QLabel("ℹ  Connectivity changes apply immediately. Sync interval changes take effect on next cycle.")
        note.setStyleSheet(f"color:{TEXT_SEC}; font-size:12px; background:transparent; border:none;")
        note.setWordWrap(True)
        lay.addWidget(note)

        # ── Windows Startup toggle (Windows only) ──────────────────
        if sys.platform == "win32":
            lay.addWidget(_h_line())
            import startup as _s
            self._startup_btn = QPushButton(
                "✓  Registered — Runs on Login" if _s.is_registered() else "Register for Windows Startup"
            )
            self._startup_btn.setObjectName("accent_btn" if _s.is_registered() else "")
            self._startup_btn.setFixedHeight(36)
            self._startup_btn.clicked.connect(self._toggle_startup)
            lay.addWidget(self._startup_btn)

        self._msg = QLabel("")
        self._msg.setStyleSheet("background:transparent; border:none;")
        self._msg.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self._msg)

        root.addWidget(card); root.addStretch()
        self._load()

    def _load(self):
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self._f_center.setText(cfg.get("center_id",             ""))
            self._f_ip.setText(    cfg.get("device_ip",             ""))
            self._f_port.setValue(int(cfg.get("device_port",        4370)))
            self._f_url.setText(   cfg.get("server_url",            ""))
            self._f_key.setText(   cfg.get("api_key",               ""))
            self._f_int.setValue(int(cfg.get("sync_interval_seconds", 30)))
        except Exception as exc:
            self._msg.setText(f'<span style="color:{ERROR}">Could not load config: {exc}</span>')

    def _save(self):
        cfg = {
            "center_id":             self._f_center.text().strip(),
            "device_ip":             self._f_ip.text().strip(),
            "device_port":           self._f_port.value(),
            "server_url":            self._f_url.text().strip(),
            "api_key":               self._f_key.text().strip(),
            "sync_interval_seconds": self._f_int.value(),
        }
        try:
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            if self._worker is not None:
                self._worker.reload_config()
                self._msg.setText(
                    f'<span style="color:{SUCCESS}">✓ Settings applied. Agent reconnecting…</span>'
                )
            else:
                self._msg.setText(
                    f'<span style="color:{SUCCESS}">✓ Saved. Restart agent to apply changes.</span>'
                )
        except Exception as exc:
            self._msg.setText(f'<span style="color:{ERROR}">Save failed: {exc}</span>')

    def _test_device(self):
        ip   = self._f_ip.text().strip()
        port = self._f_port.value()
        if not ip:
            self._msg.setText(f'<span style="color:{WARNING}">Enter a Device IP first.</span>')
            return

        def _do():
            from zk import ZK
            zk_inst = ZK(ip, port=port, timeout=5, ommit_ping=True)
            conn = zk_inst.connect()
            try:
                return conn.get_device_name()
            finally:
                try:
                    conn.disconnect()
                except Exception:
                    pass

        self._msg.setText(f'<span style="color:{INFO}">Testing device connection…</span>')
        loader = DataLoader(_do, self)
        loader.result.connect(
            lambda name: self._msg.setText(
                f'<span style="color:{SUCCESS}">✓ Device connected: {name}</span>'
            )
        )
        loader.error.connect(
            lambda e: self._msg.setText(
                f'<span style="color:{ERROR}">✗ Device unreachable: {e}</span>'
            )
        )
        loader.start()

    def _test_server(self):
        import requests as _req
        url = self._f_url.text().strip().rstrip("/")
        key = self._f_key.text().strip()
        cid = self._f_center.text().strip()
        if not url:
            self._msg.setText(f'<span style="color:{WARNING}">Enter a Server URL first.</span>')
            return

        def _do():
            try:
                resp = _req.get(
                    f"{url}/attendance-sync/unregistered-users",
                    headers={"X-Api-Key": key, "X-Center-Id": cid},
                    timeout=8,
                )
                if resp.status_code == 200:
                    return "Server reachable — credentials valid"
                return f"Server reachable (HTTP {resp.status_code})"
            except _req.exceptions.ConnectionError:
                raise Exception("Cannot connect to server")
            except _req.exceptions.Timeout:
                raise Exception("Server did not respond in time")
            except _req.exceptions.SSLError as exc:
                raise Exception(f"SSL error: {exc}") from exc

        self._msg.setText(f'<span style="color:{INFO}">Testing server connection…</span>')
        loader = DataLoader(_do, self)
        loader.result.connect(
            lambda msg: self._msg.setText(f'<span style="color:{SUCCESS}">✓ {msg}</span>')
        )
        loader.error.connect(
            lambda e: self._msg.setText(f'<span style="color:{ERROR}">✗ {e}</span>')
        )
        loader.start()

    def _toggle_startup(self):
        import startup as _s
        if _s.is_registered():
            _s.unregister()
            self._startup_btn.setText("Register for Windows Startup")
            self._startup_btn.setObjectName("")
        else:
            _s.register()
            self._startup_btn.setText("✓  Registered — Runs on Login")
            self._startup_btn.setObjectName("accent_btn")
        self._startup_btn.style().unpolish(self._startup_btn)
        self._startup_btn.style().polish(self._startup_btn)


# ─────────────────────────────────────────────────────────────────
#  Add Student dialog
# ─────────────────────────────────────────────────────────────────

class _AddStudentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_uid  = 0
        self.result_name = ""
        self.setWindowTitle("Add Student to Device")
        self.setFixedSize(380, 200)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18); lay.setSpacing(14)
        lay.addWidget(_section_label("New Student")); lay.addWidget(_h_line())

        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._uid_spin = QSpinBox(); self._uid_spin.setRange(1, 9999); self._uid_spin.setFixedHeight(36)
        self._name_edit = QLineEdit(); self._name_edit.setMaxLength(24); self._name_edit.setFixedHeight(36)
        self._name_edit.setPlaceholderText("Full name (max 24 chars)")
        form.addRow(_dim_label("UID"),  self._uid_spin)
        form.addRow(_dim_label("Name"), self._name_edit)
        lay.addLayout(form)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setFixedHeight(36); cancel.clicked.connect(self.reject)
        ok = QPushButton("Add to Device"); ok.setObjectName("accent_btn")
        ok.setFixedHeight(36); ok.clicked.connect(self._ok)
        btns.addWidget(cancel); btns.addWidget(ok)
        lay.addLayout(btns)

    def _ok(self):
        name = self._name_edit.text().strip()
        if not name:
            self._name_edit.setPlaceholderText("⚠ Name is required!"); return
        self.result_uid = self._uid_spin.value()
        self.result_name = name
        self.accept()


# ═════════════════════════════════════════════════════════════════
#  Main Dashboard window
# ═════════════════════════════════════════════════════════════════

_NAV = [
    ("📊", "Overview"),
    ("👥", "Students"),
    ("🕐", "Attendance"),
    ("", "Activity Log"),
    ("⚙️",  "Settings"),
]


class DashboardWindow(QMainWindow):
    def __init__(self, worker: SyncWorker, parent=None):
        super().__init__(parent)
        self._worker = worker
        self.setWindowTitle("BASU Biometric Agent")
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(STYLESHEET)

        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0); vbox.setSpacing(0)

        vbox.addWidget(self._build_top_bar())

        # Sync-in-progress banner (hidden when idle)
        self._sync_banner = QLabel("🔄  Syncing with server…")
        self._sync_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sync_banner.setFixedHeight(28)
        self._sync_banner.setStyleSheet(
            f"background-color:{WARNING}22; color:{WARNING};"
            f" font-size:12px; border-bottom:1px solid {WARNING}66;"
            f" padding:0; margin:0;"
        )
        self._sync_banner.hide()
        vbox.addWidget(self._sync_banner)

        body = QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_stack(), stretch=1)
        vbox.addLayout(body, stretch=1)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        t = QTimer(self); t.timeout.connect(self._tick); t.start(5_000)
        self._tick()
        self._switch(0)

    # ── Top bar ───────────────────────────────────────────────────

    def _build_top_bar(self) -> QWidget:
        bar = QWidget(); bar.setObjectName("TopBar"); bar.setFixedHeight(52)
        lay = QHBoxLayout(bar); lay.setContentsMargins(20, 0, 20, 0)

        title = QLabel("BASU Biometric Agent")
        title.setStyleSheet(
            f"color:{TEXT_PRI}; font-size:16px; font-weight:bold; background:transparent; border:none;"
        )
        center_lbl = _dim_label(f"Center: {config.CENTER_ID}")

        self._top_status = QLabel("● Connecting…")
        self._top_status.setStyleSheet(f"color:{TEXT_SEC}; font-size:13px; background:transparent; border:none;")
        self._top_status.setTextFormat(Qt.TextFormat.RichText)

        sync_btn = QPushButton("⟳  Sync Now")
        sync_btn.setObjectName("sync_btn"); sync_btn.setFixedHeight(34)
        sync_btn.clicked.connect(self._on_sync)

        lay.addWidget(title); lay.addSpacing(20); lay.addWidget(center_lbl)
        lay.addStretch(); lay.addWidget(self._top_status); lay.addSpacing(16); lay.addWidget(sync_btn)
        return bar

    # ── Sidebar ───────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sb = QWidget(); sb.setObjectName("Sidebar"); sb.setFixedWidth(200)
        lay = QVBoxLayout(sb); lay.setContentsMargins(10, 16, 10, 16); lay.setSpacing(4)
        lay.addWidget(_section_label("Navigation")); lay.addSpacing(6)

        self._nav_btns: list[QPushButton] = []
        for i, (icon, label) in enumerate(_NAV):
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("nav_btn"); btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, idx=i: self._switch(idx))
            self._nav_btns.append(btn); lay.addWidget(btn)

        lay.addStretch()
        return sb

    # ── Stacked pages ─────────────────────────────────────────────

    def _build_stack(self) -> QStackedWidget:
        self._stack = QStackedWidget()
        self._pages = [
            OverviewPage(self._worker),
            StudentsPage(self._worker),
            AttendancePage(self._worker),
            LogPage(),
            SettingsPage(self._worker),
        ]
        for p in self._pages:
            self._stack.addWidget(p)
        return self._stack

    # ── Navigation ────────────────────────────────────────────────

    def _switch(self, idx: int):
        for i, btn in enumerate(self._nav_btns):
            btn.setProperty("active", i == idx)
            btn.style().unpolish(btn); btn.style().polish(btn)
        self._stack.setCurrentIndex(idx)

    # ── Sync Now ──────────────────────────────────────────────────

    def _on_sync(self):
        self._worker.run_once()
        self._top_status.setText(f'<span style="color:{INFO}">● Syncing…</span>')
        QTimer.singleShot(3000, self._tick)

    # ── Status tick ───────────────────────────────────────────────

    def _tick(self):
        with self._worker._lock:
            syncing   = self._worker.syncing
        self._sync_banner.setVisible(syncing)

        online    = self._worker.device_online
        server_ok = self._worker.server_reachable
        last_sync = self._worker.last_sync_time
        err       = self._worker.last_error
        nsi       = self._worker.next_sync_in

        dot   = f'<span style="color:{SUCCESS if online else ERROR}">●</span>'
        state = f'<span style="color:{TEXT_PRI if online else TEXT_SEC}"> {"Online" if online else "Offline"}</span>'
        self._top_status.setText(dot + state)

        sync_str    = last_sync.strftime("%H:%M:%S") if last_sync else "—"
        next_str    = f"  |  Next sync: {nsi}s" if nsi > 0 else ""
        server_str  = f"  |  Server: {'OK' if server_ok else 'Unreachable'}"
        err_part    = f"  |  ⚠ {err}" if err and not online else ""
        self._statusbar.showMessage(
            f"{'● Online' if online else '○ Offline'}"
            f"  |  Last sync: {sync_str}"
            f"{next_str}"
            f"{server_str}"
            f"  |  Worker: Running"
            f"{err_part}"
        )

