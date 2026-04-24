[Setup]
AppName=Sistema de Abasto
AppVersion=1.0
AppPublisher=Evero Desarrollo
DefaultDirName={autopf}\SistemaAbasto
DefaultGroupName=Sistema de Abasto
OutputDir=instalador
OutputBaseFilename=SistemaAbasto_Instalador_v1.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Opciones adicionales:"
Name: "startupicon"; Description: "Iniciar automaticamente con Windows"; GroupDescription: "Opciones adicionales:"

[Files]
Source: "dist\SistemaAbasto.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Sistema de Abasto"; Filename: "{app}\SistemaAbasto.exe"
Name: "{group}\Desinstalar Sistema de Abasto"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Sistema de Abasto"; Filename: "{app}\SistemaAbasto.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SistemaAbasto"; ValueData: """{app}\SistemaAbasto.exe"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\SistemaAbasto.exe"; Description: "Iniciar Sistema de Abasto ahora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\backups"