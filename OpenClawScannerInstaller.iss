#define MyAppName "OpenClaw Scanner"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "OpenClaw"
#define MyAppExeName "OpenClawScanner.exe"

[Setup]
AppId={{4E1C7DAA-6E57-4A5A-AE7A-2F88F087CF91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\OpenClaw Scanner
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist\installer
OutputBaseFilename=OpenClawScannerSetup
SetupIconFile=assets\openclaw.ico
WizardStyle=modern
WizardImageFile=assets\installer_wizard.bmp
WizardSmallImageFile=assets\installer_small.bmp
Compression=lzma2/max
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
AppMutex=OpenClawScannerDesktopMutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\OpenClawScanner\.env"; DestDir: "{app}"; Flags: onlyifdoesntexist ignoreversion skipifsourcedoesntexist
Source: "dist\OpenClawScanner\*"; DestDir: "{app}"; Excludes: ".env"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\openclaw.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\openclaw.ico"
Name: "{autoprograms}\Reset OpenClaw State"; Filename: "{app}\ResetScannerState.bat"; IconFilename: "{app}\openclaw.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
