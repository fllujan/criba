; Instalador de Criba para Windows (Inno Setup 6.3 o posterior).
; Uso, tras PyInstaller y desde la raíz del repositorio:
;   iscc /DAppVersion=1.0.0 packaging\windows\criba.iss
; Deja dist\Criba-Setup-<versión>.exe.
;
; Se instala por usuario y sin permisos de administrador (el estudiante no siempre los
; tiene); quien quiera puede elegir instalar para todos. Desinstalar no borra los PDF
; generados ni la caché.

#ifndef AppVersion
  #error Falta /DAppVersion=x.y.z
#endif

[Setup]
AppId={{11655E30-2949-47B9-B5A6-275778AD5D1A}
AppName=Criba
AppVersion={#AppVersion}
AppVerName=Criba {#AppVersion}
AppPublisher=Félix Luján
AppPublisherURL=https://github.com/fllujan/criba
AppSupportURL=https://github.com/fllujan/criba/issues
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Criba
DefaultGroupName=Criba
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist
OutputBaseFilename=Criba-Setup-{#AppVersion}
SetupIconFile=criba.ico
UninstallDisplayIcon={app}\Criba.exe
UninstallDisplayName=Criba
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\Criba\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Criba"; Filename: "{app}\Criba.exe"
Name: "{autodesktop}\Criba"; Filename: "{app}\Criba.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Criba.exe"; Description: "{cm:LaunchProgram,Criba}"; Flags: nowait postinstall skipifsilent
