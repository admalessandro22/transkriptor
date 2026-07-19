@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal EnableExtensions

echo ============================================
echo   Transkriptor — instalador
echo ============================================
echo.

echo [1/5] Verificando Python 3.12+...
python scripts\instalar_helper.py --check python
if errorlevel 1 (
  echo Instale Python 3.12+ e tente novamente.
  pause
  exit /b 1
)

echo [2/5] Criando ambiente virtual .venv...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo [ERRO] Falha ao criar .venv
    pause
    exit /b 1
  )
)
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "VENV_PIP=%~dp0.venv\Scripts\pip.exe"

echo [3/5] Instalando PyTorch (GPU se disponivel)...
python scripts\instalar_helper.py --check gpu
for /f "delims=" %%C in ('%VENV_PY% scripts\instalar_helper.py --check torch') do set "TORCH_CMD=%%C"
REM helper imprime comando com sys.executable do helper — instala via venv
%VENV_PY% -m pip install --upgrade pip
%VENV_PY% scripts\instalar_helper.py --check gpu >nul 2>&1
%VENV_PY% -c "from scripts.instalar_helper import tem_gpu_nvidia, comando_torch; import subprocess,sys; cmd=comando_torch(tem_gpu_nvidia()); cmd[0]=sys.executable; print(' '.join(cmd)); raise SystemExit(subprocess.call(cmd))"
if errorlevel 1 (
  echo [AVISO] Falha no torch CUDA/CPU automatico — tentando CPU...
  %VENV_PY% -m pip install torch torchaudio
)

echo [4/5] Dependencias do projeto + warm-up opcional...
%VENV_PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERRO] Falha ao instalar requirements.txt
  pause
  exit /b 1
)
echo.
echo Deseja baixar modelos Whisper/voz agora? (S/N)
set /p WARMUP=
if /I "%WARMUP%"=="S" (
  %VENV_PY% scripts\warmup_modelos.py
)
python scripts\instalar_helper.py --check ollama

echo [5/5] Criando atalho...
for /f "delims=" %%P in ('%VENV_PY% scripts\resolver_pythonw.py') do set "PYTHONW=%%P"
if not defined PYTHONW (
  echo [ERRO] pythonw.exe nao encontrado.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\criar_atalho_desktop.ps1" ^
  -Pythonw "%PYTHONW%" ^
  -Aplicativo "%~dp0transkriptor.pyw" ^
  -Icone "%~dp0transkriptor.ico"
if errorlevel 1 (
  echo [ERRO] Falha ao criar atalho.
  pause
  exit /b 1
)

for /f "delims=" %%V in ('%VENV_PY% -c "from config import VERSAO; print(VERSAO)"') do set "VERSAO=%%V"
echo.
echo ============================================
echo   Instalacao Transkriptor %VERSAO% concluida!
echo   Use o atalho "Transkriptor" ou iniciar_bandeja.bat
echo ============================================
pause
