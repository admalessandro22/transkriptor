@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal EnableExtensions

echo Iniciando transcritor de reunioes...
echo.

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  set "PY_RUN=%VENV_PY%"
) else (
  set "PY_RUN=python"
  echo [AVISO] .venv ausente; usando Python do sistema. Rode instalar.bat.
)

for /f "delims=" %%P in ('"%PY_RUN%" scripts\resolver_pythonw.py 2^>nul') do set "PYTHONW=%%P"
if not defined PYTHONW (
  echo [AVISO] resolver_pythonw sem resposta; seguindo com %PY_RUN%.
)

"%PY_RUN%" transcrever_meet.py %*
pause
