@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Iniciando Transkriptor na bandeja do sistema...
echo.

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  for /f "delims=" %%P in ('"%VENV_PY%" scripts/resolver_pythonw.py 2^>nul') do set "PYTHONW=%%P"
) else (
  for /f "delims=" %%P in ('python scripts/resolver_pythonw.py 2^>nul') do set "PYTHONW=%%P"
)

if not defined PYTHONW (
    echo [ERRO] Python nao encontrado. Rode instalar.bat
    pause
    exit /b 1
)

if not exist "%PYTHONW%" (
    echo [ERRO] pythonw.exe nao encontrado em: %PYTHONW%
    pause
    exit /b 1
)

start "" "%PYTHONW%" "%~dp0transkriptor.pyw"
echo.
echo Transkriptor iniciado. Procure o icone do microfone na bandeja ^(seta ^ na barra de tarefas^).
ping -n 4 127.0.0.1 >nul
