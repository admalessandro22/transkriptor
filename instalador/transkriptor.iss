; Transkriptor — instalador por usuário (T-15.E4 / FR-15.E4, DP-15-06).
; Sem administrador e sem Python prévio: o uv embutido baixa o Python 3.12
; gerenciado e aplica o lockfile com hash (CPU ou CUDA, detectado).
; Build: ISCC.exe /DVersao=x.y.z instalador\transkriptor.iss  (uv.exe em instalador\bin\)

#ifndef Versao
  #define Versao "0.0.0-dev"
#endif

[Setup]
AppId={{6A3F1E52-7C1B-4F0A-9E5B-2B7D1C0F9A11}
AppName=Transkriptor
AppVersion={#Versao}
AppPublisher=Transkriptor
DefaultDirName={localappdata}\Programs\Transkriptor
DefaultGroupName=Transkriptor
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=TranskriptorSetup
SetupIconFile=..\transkriptor.ico
UninstallDisplayIcon={app}\transkriptor.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalho"; Description: "Criar atalho na área de trabalho"
Name: "iniciar"; Description: "Abrir o Transkriptor junto com o Windows"

[Files]
Source: "..\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: "transcricoes,config_user.json,tests,.venv,node_modules,*.log,_modelo_voz,.git,.worktrees,test-results,dist,__pycache__,docs,*.lock,debug.log,diagnostico_*.txt,design,.github,.grok,.claude,.pytest_cache,.ci-venv,.gitignore,package.json,package-lock.json,playwright.config.js,requirements-dev.txt"
Source: "..\requirements\*.lock"; DestDir: "{app}\requirements"; Flags: ignoreversion
Source: "bin\uv.exe"; DestDir: "{app}\instalador\bin"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Transkriptor"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\transkriptor.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\transkriptor.ico"
Name: "{userdesktop}\Transkriptor"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\transkriptor.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\transkriptor.ico"; Tasks: atalho
Name: "{userstartup}\Transkriptor"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\transkriptor.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\transkriptor.ico"; Tasks: iniciar

[Run]
Filename: "{app}\instalador\bin\uv.exe"; Parameters: "run --python 3.12 --no-project ""{app}\instalador\provisionar.py"" --rota auto --uv ""{app}\instalador\bin\uv.exe"""; WorkingDir: "{app}"; StatusMsg: "Preparando o Transkriptor (baixa o Python e as bibliotecas; pode levar alguns minutos)..."; Flags: runhidden waituntilterminated
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\transkriptor.pyw"""; WorkingDir: "{app}"; Description: "Abrir o Transkriptor"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\instalador\bin\uv.exe"; Parameters: "run --python 3.12 --no-project ""{app}\instalador\provisionar.py"" --desinstalar"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "DesregistrarHost"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: files; Name: "{app}\instalador\ollama-detectado.txt"

[Code]
{ Página final: mostra o que o provisionamento encontrou do Ollama. }
procedure CurPageChanged(CurPageID: Integer);
var
  Texto: AnsiString;
begin
  if (CurPageID = wpFinished) and LoadStringFromFile(ExpandConstant('{app}\instalador\ollama-detectado.txt'), Texto) then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 + String(Texto);
end;
