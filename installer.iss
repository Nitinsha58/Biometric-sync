; installer.iss — Inno Setup 6 script for BASU Biometric Agent
;
; Requirements:
;   1. Build the exe first:  cd basu-agent && pyinstaller build.spec
;   2. Install Inno Setup 6: https://jrsoftware.org/isinfo.php
;   3. Compile:  iscc installer.iss   (or open in Inno Setup IDE)
;
; Output: Output\BASU_Biometric_Agent_Setup.exe

#define AppName      "BASU Biometric Agent"
#define AppVersion   "1.0.0"
#define AppPublisher "BASU Education"
#define AppExeName   "BASU_Biometric_Agent.exe"

[Setup]
AppId={{9F4A2C1B-3E8D-4F7A-B2C5-1D6E8F9A0B3C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://basueducation.com
DefaultDirName={autopf}\BASU Biometric Agent
DefaultGroupName={#AppName}
OutputDir=Output
OutputBaseFilename=BASU_Biometric_Agent_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; No admin required — agent runs per-user
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExeName}
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";     Description: "Create a &desktop shortcut";                    GroupDescription: "Additional icons:"
Name: "startupregistry"; Description: "Start agent automatically when &Windows starts"; GroupDescription: "Startup:"

[Files]
; PyInstaller single-file exe
Source: "basu-agent\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Windows startup — mirrors the toggle in the dashboard Settings page
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "BASU_Biometric_Agent"; \
    ValueData: """{app}\{#AppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startupregistry

[Run]
; Launch directly after install
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName} now"; \
    Flags: nowait postinstall skipifsilent
