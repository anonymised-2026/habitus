; ============================================================
; HABITUS v1.0 – Inno Setup Installer Script
; Build:  ISCC habitus_setup.iss
; Output: installer\HABITUS_Setup_v1.0.exe
; ============================================================

#define AppName      "HABITUS"
#define AppVersion   "1.0"
#define AppFullVer   "1.0.0"
#define AppPublisher "Ö. K. Örücü & S. Örücü"
#define AppURL       "https://github.com/omerorucu/habitus"
#define AppExeName   "HABITUS.exe"
#define SourceDir    "dist\HABITUS"

[Setup]
AppId                    = {{A3F2C1D4-7E5B-4A9F-8C3D-2B1E6F0A4D7C}
AppName                  = {#AppName}
AppVersion               = {#AppVersion}
AppVerName               = {#AppName} v{#AppVersion}
AppPublisher             = {#AppPublisher}
AppPublisherURL          = {#AppURL}
AppSupportURL            = {#AppURL}/issues
AppUpdatesURL            = {#AppURL}/releases
DefaultDirName           = {autopf}\HABITUS
DefaultGroupName         = HABITUS
AllowNoIcons             = yes
LicenseFile              = LICENSE.txt
OutputDir                = installer
OutputBaseFilename       = HABITUS_Setup_v{#AppVersion}
SetupIconFile            = icon.ico
Compression              = lzma2/ultra64
SolidCompression         = yes
InternalCompressLevel    = ultra64
ArchitecturesAllowed     = x64compatible
ArchitecturesInstallIn64BitMode = x64compatible
WizardStyle              = modern
WizardSizePercent        = 120
DisableProgramGroupPage  = yes
UninstallDisplayIcon     = {app}\{#AppExeName}
UninstallDisplayName     = {#AppName} v{#AppVersion}
VersionInfoVersion       = {#AppFullVer}
VersionInfoCompany       = {#AppPublisher}
VersionInfoDescription   = HABITUS Species Distribution Modelling Toolkit
VersionInfoCopyright     = Copyright 2026 {#AppPublisher}
MinVersion               = 10.0.17763
CloseApplications        = yes
RestartIfNeededByRun     = no

; ── Installer appearance ──────────────────────────────────────────────────────
WizardImageFile          = compiler:WizClassicImage.bmp
WizardSmallImageFile     = compiler:WizClassicSmallImage.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";     Description: "Create a &desktop shortcut";         GroupDescription: "Additional icons:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Create a &Quick Launch shortcut";    GroupDescription: "Additional icons:"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
; Main executable
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; All bundled dependencies (the _internal folder)
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"; \
      Comment: "HABITUS Species Distribution Modelling Toolkit"
Name: "{group}\Uninstall {#AppName}";    Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";      Filename: "{app}\{#AppExeName}"; \
      Tasks: desktopicon; \
      Comment: "HABITUS Species Distribution Modelling Toolkit"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; \
      Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName} now"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
// Show a friendly message if the system is 32-bit
function InitializeSetup(): Boolean;
begin
  if not Is64BitInstallMode then
  begin
    MsgBox('HABITUS requires a 64-bit version of Windows 10 (build 17763) or later.', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;
