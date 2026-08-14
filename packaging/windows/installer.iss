#define MyAppName "AI PM LAB Privacy Gate"
#define MyAppVersion "0.4.0"
#define MyAppVersionInfo "0.4.0.1"
#define MyAppPublisher "AI PM LAB by Trigosat Consulting"
#define MyAppExeName "AI PM LAB Privacy Gate.exe"
#define MyAppId "{{2F5D4173-04C2-46F2-BE8D-3FC0FBC2EE17}"

#ifndef DistDir
  #define DistDir "..\..\dist\AI PM LAB Privacy Gate"
#endif

#ifndef ReleaseDir
  #define ReleaseDir "..\..\release"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#ReleaseDir}
OutputBaseFilename=AI_PM_LAB_Privacy_Gate_Setup_{#MyAppVersion}
; ZIP and non-solid packaging are larger, but easier for endpoint protection
; products to inspect and less prone to heuristic false positives.
Compression=zip
SolidCompression=no
WizardStyle=modern
SetupIconFile=..\..\resources\branding\privacy-gate.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; MCP-enabled builds minimize to the notification area on a normal close.
; During an update, Restart Manager must be allowed to terminate the old process.
CloseApplications=force
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersionInfo}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersionInfo}
AppPublisherURL=https://www.linkedin.com/in/pietro-forestieri/
AppSupportURL=mailto:peter@propertydex.xyz

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { A tray/background update can outlive the visible window. Terminate the }
  { installed app process tree, then explicitly remove an orphaned MCP child }
  { so the new build can bind its stable loopback port immediately. }
  Exec(ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM "{#MyAppExeName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'),
    '/F /IM "AI PM LAB Privacy Gate MCP.exe"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
