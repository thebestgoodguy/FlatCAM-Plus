#define AppName "FlatCAM Plus"
#define AppExeName "FlatCAMPlus.exe"
#define AppPublisher "FlatCAM Plus"

#ifndef AppVersion
#define AppVersion "1.1.0"
#endif

#ifndef AppArch
#define AppArch "x64"
#endif

#ifndef AppInstallerArch
#define AppInstallerArch AppArch
#endif

#ifndef AppIconFile
#define AppIconFile "..\..\build\icons\FlatCAMPlus.ico"
#endif

#define AppSourceDir "..\..\dist\windows\" + AppArch + "\FlatCAMPlus"

[Setup]
#if AppArch == "x64"
AppId={{E8B48C3C-7F1D-4B38-9F74-2C8DE02D4B9F}
#else
AppId={{B9C1DF26-318D-42DD-9D55-E84286B9F982}
#endif
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\FlatCAMPlus
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=FlatCAMPlus-Setup-{#AppVersion}-{#AppInstallerArch}
SetupIconFile={#AppIconFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
#if AppArch == "x64"
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
#endif
UninstallDisplayIcon={app}\FlatCAMPlus.ico
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#AppIconFile}"; DestDir: "{app}"; DestName: "FlatCAMPlus.ico"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{autoprograms}\{#AppName}.lnk"
Type: files; Name: "{autodesktop}\{#AppName}.lnk"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\FlatCAMPlus.ico"; IconIndex: 0
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\FlatCAMPlus.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
