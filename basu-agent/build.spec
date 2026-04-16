# build.spec — PyInstaller packaging config for BASU Biometric Agent
#
# Build command (run on Windows from the basu-agent\ folder):
#   pip install pyinstaller
#   pyinstaller build.spec
#
# Output: dist\BASU_Biometric_Agent.exe  (single-file, no console window)
#
# The bundled config.json is a template only.  On first launch the exe
# copies it to %APPDATA%\BASU_Biometric_Agent\config.json where the
# operator can edit it safely without admin rights.

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        ("config.json", "."),   # bundled default config template
    ],
    hiddenimports=[
        # pyzk
        "zk",
        "zk.base",
        "zk.exception",
        "zk.user",
        "zk.attendance",
        # PyQt6
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "PyQt6.QtCore",
        "PyQt6.sip",
        # requests / network stack
        "requests",
        "certifi",
        "charset_normalizer",
        "idna",
        "urllib3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BASU_Biometric_Agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets\\icon.ico",   # add a 256x256 icon.ico and uncomment
)


import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        ("config.json", "."),   # bundle default config alongside the exe
    ],
    hiddenimports=[
        # pyzk internals
        "zk",
        "zk.base",
        "zk.exception",
        "zk.user",
        "zk.attendance",
        # PyQt6 platform plugin (needed for Windows)
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "PyQt6.QtCore",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BASU_Biometric_Agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window — silent background agent
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",   # uncomment and add icon.ico for a custom tray icon
)
