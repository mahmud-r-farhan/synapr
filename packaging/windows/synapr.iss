; Inno Setup Script for Synapr
; Creates an installer with MIT License display, shortcut toggles,
; Zero Data Leak guarantee notice, and custom application icon.

#define MyAppName "Synapr"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Synapr Maintainers"
#define MyAppURL "https://github.com/mahmud-r-farhan/synapr"
#define MyAppExeName "synapr.exe"

[Setup]
AppId={{5F7C38B1-0D4A-483A-8F7E-3829035B741E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
InfoBeforeFile=privacy_notice.txt
SetupIconFile=..\..\synapr\assets\image.ico
UninstallDisplayIcon={app}\assets\image.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=no
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
OutputBaseFilename=Synapr-Setup-x64
OutputDir=..\..\dist

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "addtopath"; Description: "Add Synapr to PATH environment variable (CLI access)"; GroupDescription: "System Integration:"

[Files]
Source: "..\..\dist\synapr\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\synapr\assets\image.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\readme.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "ui --open-browser"; IconFilename: "{app}\assets\image.ico"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppName}\{#MyAppName} Web Dashboard"; Filename: "{app}\{#MyAppExeName}"; Parameters: "ui --open-browser"; IconFilename: "{app}\assets\image.ico"; Tasks: startmenuicon
Name: "{autoprograms}\{#MyAppName}\{#MyAppName} CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\{#MyAppExeName} --help"""; IconFilename: "{app}\assets\image.ico"; Tasks: startmenuicon
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; IconFilename: "{app}\assets\image.ico"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "ui --open-browser"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')} Web Dashboard}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKA; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Tasks: addtopath

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Param + ';', ';' + OrigPath + ';') = 0;
end;
