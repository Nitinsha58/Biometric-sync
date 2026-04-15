# BASU Biometric Agent

Background Windows agent that keeps a ZKTeco biometric attendance device in sync with the BASU Education server.

## Features

- **System tray** app — runs silently in the background from Windows startup
- **Dashboard** — open via tray icon; manage users, attendance, and device config
- **Auto-sync** — polls the server for new students, enrolls them on the device, reports fingerprint status back
- **Delete support** — individual and bulk delete of device users and attendance records
- **Hot-reload config** — change device IP / server URL / API key without restarting

---

## Project structure

```
Biometric/
├── basu-agent/          # Main application package
│   ├── main.py          # Entry point (tray icon + worker)
│   ├── dashboard.py     # PyQt6 management dashboard
│   ├── worker.py        # Background sync thread
│   ├── device.py        # ZKTeco device wrapper (pyzk)
│   ├── api.py           # HTTP client for BASU server
│   ├── config.py        # Config loader (dev + frozen)
│   ├── startup.py       # Windows Registry startup helpers
│   ├── config.json      # ← fill in your credentials before running
│   ├── requirements.txt
│   └── build.spec       # PyInstaller build config
├── installer.iss        # Inno Setup installer script
└── b_machine.py         # Standalone FastAPI device service (optional)
```

---

## Windows setup (from GitHub)

### Prerequisites

| Tool | Download |
|------|----------|
| Python 3.11+ | https://www.python.org/downloads/ |
| Git | https://git-scm.com/download/win |

### 1 — Clone

```powershell
git clone git@github.com:Nitinsha58/Biometric-sync.git
cd Biometric-sync
```

### 2 — Create virtual environment and install dependencies

```powershell
cd basu-agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3 — Configure

Edit `basu-agent\config.json` with your real values:

```json
{
  "center_id": "your_center_id",
  "device_ip": "192.168.1.201",
  "device_port": 4370,
  "server_url": "https://be.basueducation.com",
  "api_key": "your_api_key_here",
  "sync_interval_seconds": 300
}
```

### 4 — Run in dev mode

```powershell
cd basu-agent
python main.py
```

A tray icon appears. Right-click → **Open Dashboard** to manage the device.

---

## Build a standalone `.exe` installer

Do this once on the target Windows machine (or a CI runner).

### Step 1 — Build the exe

```powershell
cd basu-agent
pip install pyinstaller
pyinstaller build.spec
# Output: basu-agent\dist\BASU_Biometric_Agent.exe
```

### Step 2 — Build the installer

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. From the repo root:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
# Output: Output\BASU_Biometric_Agent_Setup.exe
```

### Installer features

- Installs to `C:\Program Files\BASU Biometric Agent\`
- Config + log stored in `%APPDATA%\BASU_Biometric_Agent\` (no admin needed to edit)
- Optional desktop shortcut
- Optional Windows startup registration
- Launches the agent immediately after install

---

## First-run on a fresh machine (installer method)

1. Copy `BASU_Biometric_Agent_Setup.exe` to the machine
2. Run the installer — tick **Start agent automatically when Windows starts**
3. Edit `%APPDATA%\BASU_Biometric_Agent\config.json` with the correct credentials
4. Right-click the tray icon → **Sync Now** to verify

---

## Configuration reference

| Key | Default | Description |
|-----|---------|-------------|
| `center_id` | — | Unique ID for this BASU center |
| `device_ip` | `192.168.1.201` | IP address of the ZKTeco device |
| `device_port` | `4370` | TCP port (default for ZKTeco) |
| `server_url` | — | BASU backend base URL |
| `api_key` | — | API key for the backend |
| `sync_interval_seconds` | `300` | How often the agent syncs (seconds) |

Changes made via the dashboard **Settings** page take effect immediately without a restart.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Tray icon stays grey | Device unreachable — check IP and that the device is on the same network |
| "Server unreachable" in status bar | Check `server_url` and `api_key` in config |
| Users show 0 after sync | Check that `biometricNumber` is set for students in the portal |
| Log file location | `%APPDATA%\BASU_Biometric_Agent\agent.log` (frozen) or `basu-agent\agent.log` (dev) |
