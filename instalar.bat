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

echo [3/5] Selecionando rota CPU/CUDA...
python scripts\instalar_helper.py --check gpu
set "ROTA="
for /f "delims=" %%R in ('python scripts\instalar_helper.py --route') do set "ROTA=%%R"
if not defined ROTA (
  echo [ERRO] Nao foi possivel selecionar CPU/CUDA.
  pause
  exit /b 1
)
python scripts\instalar_helper.py --check deps --rota %ROTA%
if errorlevel 1 (
  echo [ERRO] Combinacao de dependencias invalida para a rota %ROTA%.
  pause
  exit /b 1
)
"%VENV_PY%" scripts\instalar_helper.py --check installed-route --rota %ROTA%
if errorlevel 1 (
  echo [ERRO] Ambiente existente usa outra rota. Preserve a venv e instale em uma pasta nova.
  pause
  exit /b 1
)

echo [4/5] Instalando dependencias fixadas da rota %ROTA%...
"%VENV_PY%" -m pip install --require-hashes -r "requirements\requirements-%ROTA%.lock"
if errorlevel 1 (
  echo [ERRO] Falha ao instalar lock da rota %ROTA%.
  pause
  exit /b 1
)
"%VENV_PY%" -m pip check
if errorlevel 1 (
  echo [ERRO] Dependencias incompatíveis na rota %ROTA%.
  pause
  exit /b 1
)
"%VENV_PY%" scripts\instalar_helper.py --check installed-route --rota %ROTA% --require-installed
if errorlevel 1 (
  echo [ERRO] Pacotes torch/torchaudio nao correspondem a rota %ROTA%.
  pause
  exit /b 1
)
echo.
echo Deseja baixar modelos Whisper/voz agora? (S/N)
set /p WARMUP=
if /I "%WARMUP%"=="S" (
  "%VENV_PY%" scripts\warmup_modelos.py
)
python scripts\instalar_helper.py --check ollama

echo [5/5] Criando atalho...
for /f "delims=" %%P in ('"%VENV_PY%" scripts\resolver_pythonw.py') do set "PYTHONW=%%P"
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

set "VERSAO="
for /f "delims=" %%V in ('"%VENV_PY%" scripts\instalar_helper.py --version') do set "VERSAO=%%V"
if not defined VERSAO (
  echo [ERRO] Nao foi possivel ler a versao do produto.
  pause
  exit /b 1
)
echo.
echo ============================================
echo   Instalacao Transkriptor %VERSAO% concluida!
echo   Use o atalho "Transkriptor" ou iniciar_bandeja.bat
echo ============================================
pause
