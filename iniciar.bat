@echo off
chcp 65001 >nul
echo Iniciando transcritor de reunioes...
echo.
python transcrever_meet.py %*
pause
