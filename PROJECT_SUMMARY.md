# BASU Biometric Agent — Project Summary

## Overview

**BASU Biometric Agent** is a Windows background service that synchronizes student and attendance data between a ZKTeco biometric device and the BASU Education backend server. It automates the enrollment of new students on the device, tracks fingerprint enrollment status, manages attendance records, and provides a desktop dashboard for manual device management.

**Key Purpose**: Bridge the gap between BASU's student management system and physical biometric attendance hardware, with zero manual intervention required.

---

## Project Structure

```
Biometric/
├── basu-agent/                  # Main Windows desktop application (125+ functions/classes)
│   ├── main.py                  # System tray entry point
│   ├── worker.py                # Background sync thread (SyncWorker)
│   ├── dashboard.py             # PyQt6 management UI (multiple pages)
│   ├── device.py                # ZKTeco device wrapper (ZKDevice)
│   ├── api.py                   # HTTP client for BASU server (APIClient)
│   ├── config.py                # Config management (dev & frozen builds)
│   ├── startup.py               # Windows Registry startup helpers
│   ├── clean_device.py          # Standalone utility to wipe device data
│   ├── test_phase1.py           # Manual testing harness
│   ├── config.json              # Configuration file
│   ├── requirements.txt          # Python dependencies
│   └── build.spec               # PyInstaller build config
├── b_machine.py                 # Optional standalone FastAPI service
├── installer.iss                # Inno Setup installer configuration
└── README.md                    # User documentation
```

---

## Architecture

### Two Main Components

#### 1. **BASU Agent** (`basu-agent/`) — Windows Desktop App
**Purpose**: Core application that runs as a background system tray service

- **125 functions/classes** across 10 Python modules
- **PyQt6-based** desktop dashboard for management
- **Multi-threaded**: Tray UI on main thread, sync on background worker
- **Hot-reload**: Config changes apply immediately without restart
- **Windows-integrated**: Startup registry support, system tray presence

**Key subsystems**:
- **UI Dashboard** (8 pages): Overview, Students, Attendance, Logs, Settings, etc.
- **Sync Worker**: Polls BASU server on configurable interval, applies changes to device
- **Device Interface**: Wraps pyzk (ZKTeco Python library)
- **Config & State**: Manages credentials, device info, startup registration
- **API Client**: HTTP communication with BASU backend

#### 2. **Machine Service** (`b_machine.py`) — FastAPI Optional Service
**Purpose**: Lightweight REST API wrapper around the device (optional alternative to the tray app)

- **11 functions** for direct device operations
- **FastAPI** framework
- HTTP endpoints for sync, enrollment, data retrieval
- Useful for testing or alternative deployment models

---

## Core Features

### 1. **Auto-Sync Workflow** (SyncWorker)
- Polls BASU server every `sync_interval_seconds` (default: 5 minutes)
- Fetches unregistered students → enrolls on device
- Reports fingerprint enrollment status back to server
- Handles deletions: Remove students from device when unregistered

### 2. **Dashboard** (PyQt6)
- **Overview Page**: Device status, sync countdown, recent log entries
- **Students Page**: View enrolled users, add/delete individually or in bulk
- **Attendance Page**: View device attendance records, filter by date/name, delete records
- **Logs Page**: Application audit trail
- **Settings Page**: Configure device IP/port, server URL, API key, auto-sync interval, Windows startup

### 3. **Device Management**
- Connect to ZKTeco device via TCP (IP + port)
- Read/write user data (UID, name, privilege level)
- Manage fingerprint enrollment state
- Query and clear attendance records
- Device validation (ping test, reachability checks)

### 4. **Configuration & State**
- **config.json**: Credentials, device IP/port, server URL, sync interval
- **SQLite DB**: Stores enrolled students, attendance, logs
- **Data Directory**: Platform-specific (Windows: `%APPDATA%\BASU_Biometric_Agent\`)

### 5. **Windows Integration**
- System tray icon (green = online, grey = offline)
- Right-click menu: Open Dashboard, Sync Now, Quit
- Optional startup registration (Windows Registry)
- No admin elevation required

---

## Technology Stack

| Component        | Technology            | Purpose                              |
|------------------|-----------------------|--------------------------------------|
| UI Framework     | PyQt6                 | Desktop dashboard & tray icon        |
| Device Protocol  | pyzk (ZKTeco lib)     | Biometric device communication       |
| HTTP Client      | requests              | BASU backend API calls               |
| REST API         | FastAPI               | Optional service wrapper             |
| State Storage    | SQLite                | Students, attendance, logs           |
| Build Tool       | PyInstaller           | Standalone .exe creation             |
| Installer        | Inno Setup            | Windows installer (.exe)             |
| Language         | Python 3.11+          | Main application language            |

---

## Code Organization

### Community Structure (from code graph)
1. **basu-agent-sync** (125 nodes)
   - 14 classes (UI, worker, device interface, API client, config)
   - 111 functions (UI handlers, device ops, API calls, data management)
   - 1,205 function call dependencies
   - Cohesion: 0.17 (loose coupling — expected for a UI app)

2. **biometric-student** (11 nodes)
   - 1 FastAPI class (StudentSync model)
   - 10 utility functions (device operations, API endpoints)
   - Alternative lightweight service model

### Key Classes

| Class            | Module         | Purpose                                |
|------------------|----------------|----------------------------------------|
| `BASUAgent`      | main.py        | Tray app orchestrator                  |
| `SyncWorker`     | worker.py      | Background sync thread                 |
| `DashboardWindow`| dashboard.py   | Main UI window (multi-page)            |
| `ZKDevice`       | device.py      | Device wrapper (connect, read/write)   |
| `APIClient`      | api.py         | BASU backend HTTP client               |

---

## Key Workflows

### 1. **Startup**
```
main() → BASUAgent → creates tray icon + SyncWorker
       → posts device info to server
       → loads config (device IP, server URL, API key)
       → optionally registers Windows startup
```

### 2. **Background Sync Cycle** (every 5 minutes)
```
SyncWorker.run() → loop every interval
                 → fetch unregistered students from API
                 → set each user on device (uid, name, privilege)
                 → fetch device enrollment status
                 → post fingerprint status back to API
                 → handle deletions (remove from device)
```

### 3. **Dashboard Interaction**
```
DashboardWindow (6 pages)
├─ OverviewPage     → Device status, sync timer, recent logs
├─ StudentsPage     → Load from DB, add new, delete (single/bulk)
├─ AttendancePage   → Query device records, filter, delete
├─ LogPage          → View operation logs
├─ SettingsPage     → Hot-reload config, test connections
└─ Data is synced via threading (DataLoader, callbacks)
```

### 4. **Configuration Reload**
- User edits settings in dashboard → calls `config.reload()`
- All modules pick up new values (device IP, sync interval, etc.)
- No restart required

---

## Configuration Reference

**File**: `basu-agent/config.json` or `%APPDATA%\BASU_Biometric_Agent\config.json`

| Key                     | Type   | Default         | Description                       |
|-------------------------|--------|-----------------|-----------------------------------|
| `center_id`             | string | —               | Unique ID for this BASU center    |
| `device_ip`             | string | `192.168.1.201` | ZKTeco device IP address          |
| `device_port`           | int    | `4370`          | ZKTeco TCP port                   |
| `server_url`            | string | —               | BASU backend base URL             |
| `api_key`               | string | —               | API key for authentication        |
| `sync_interval_seconds` | int    | `300`           | Poll interval (5 minutes)         |

---

## Development & Build

### Development Setup
```bash
cd basu-agent
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### Build Standalone Executable
```bash
pip install pyinstaller
pyinstaller build.spec
# Output: basu-agent/dist/BASU_Biometric_Agent.exe
```

### Build Windows Installer
```bash
# Requires Inno Setup 6 installed
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
# Output: Output\BASU_Biometric_Agent_Setup.exe
```

---

## Key Design Decisions

1. **PyQt6 + System Tray**: Provides native Windows integration with minimal overhead
2. **Background Worker Thread**: Sync doesn't block UI; users can open dashboard while syncing
3. **SQLite for State**: Lightweight, no server dependency, survives restarts
4. **Hot-reload Config**: Changes apply immediately without restart (improves UX)
5. **Dual Architecture**: Main tray app + optional FastAPI service for flexibility
6. **Loose Cohesion**: UI, logic, and device layers are loosely coupled (expected for a desktop app)

---

## Common Use Cases

1. **First Installation**: Run installer → edit config.json → tray icon appears
2. **Manual Sync**: Right-click tray → "Sync Now" (useful for testing)
3. **Add Student**: Dashboard → Students → "Add" (enrolls on device + posts to server)
4. **Clear Attendance**: Dashboard → Attendance → "Clear All" (removes old records)
5. **Change Settings**: Dashboard → Settings → edit → changes apply immediately
6. **Troubleshooting**: Check logs in `%APPDATA%\BASU_Biometric_Agent\agent.log`

---

## Testing & Utilities

- **test_phase1.py**: Manual testing harness (prints device info, tests API calls)
- **clean_device.py**: Standalone script to wipe device data (useful for testing)
- **config.py**: Handles both dev (file-based) and frozen (bundled) configs

---

## Data Flow Summary

```
┌──────────────────┐
│ BASU Server      │ (backend.basueducation.com)
└────────┬─────────┘
         │ API (APIClient)
         │
    ┌────▼──────────────┐
    │ BASU Agent (Tray) │
    └────┬──────────────┘
         │ pyzk
    ┌────▼──────────────┐
    │ ZKTeco Device     │ (192.168.1.201:4370)
    └───────────────────┘
         │ TCP
    ┌────▼──────────────┐
    │ Biometric Reader  │
    └───────────────────┘

SQLite DB (local):
- Students (UID, name, fingerprint status)
- Attendance (check-in/out records)
- Logs (operation history)
```

---

## Status

- **Latest Commit**: Initial commit: BASU Biometric Agent
- **Graph Stats**: 147 nodes, 1,446 edges, 11 files, 122 functions, 14 classes
- **Languages**: Python (100%)
- **Graph Updated**: 2026-04-17

---

## Next Steps for Development

1. **Hardening**: Add retry logic, exponential backoff for failed sync cycles
2. **Testing**: Unit tests for device interface, API client, config manager
3. **Monitoring**: Health check endpoint, metrics export
4. **Documentation**: API docs for FastAPI service, troubleshooting guide
5. **Optimization**: Batch device operations, caching of enrollment status
