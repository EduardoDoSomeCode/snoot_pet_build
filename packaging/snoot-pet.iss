; Inno Setup para el instalador de Windows.
;
; Se compila con:
;   iscc /DAppVersion=1.0.0 packaging\snoot-pet.iss
;
; Instala el build one-dir de PyInstaller (no el one-file): arranca mucho
; mas rapido porque no tiene que descomprimirse en un temporal cada vez.
;
; La version y el icono entran por defines para que el workflow no tenga que
; editar este fichero.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\dist\snoot-pet"
#endif

#ifndef IconFile
  #define IconFile "icons\snoot-pet.ico"
#endif

#define AppName "Snoot pet"
#define AppExeName "snoot-pet.exe"
#define AppPublisher "Snoot pet"
#define AppURL "https://github.com/snoot-pet/snoot-pet"

[Setup]
AppId={{6C1E4C0B-3D5A-4E77-9B21-7F0A2C5D8E14}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\Snoot pet
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=SnootPet-Setup-{#AppVersion}-x64
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; La pet se queda en /opt y no escribe en el directorio de instalacion, asi
; que hace falta /ALLUSERS para que el uninstaller de Inno no se meta en
; Program Files y se quede sin permiso al arrancar.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=no
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Los personajes que importa el usuario no se tocan: viven en
; %APPDATA%\Snoot_pet y se quedan al desinstalar.
Type: filesandordirs; Name: "{app}"