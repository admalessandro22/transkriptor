@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Iniciando Transkriptor na bandeja do sistema...
echo.

for /f "delims=" %%P in ('python scripts/resolver_pythonw.py 2^>nul') do set "PYTHONW=%%P"
if not defined PYTHONW (
    echo [ERRO] Python nao encontrado. Instale Python 3.12+ e rode instalar.bat
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