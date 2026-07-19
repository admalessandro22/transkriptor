@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Transkriptor — desinstalador
echo ============================================
echo.
echo Acoes previstas:
echo   - Remover atalho da Area de Trabalho (Transkriptor.lnk)
echo   - Remover atalho Startup se existir
echo   - Remover pasta .venv
echo.
echo Dados do usuario (transcricoes/, audio/, _modelo_voz/, config_user.json)
echo serao PRESERVADOS por padrao.
echo.

set /p CONF=Continuar? (S/N): 
if /I not "%CONF%"=="S" (
  echo Cancelado.
  pause
  exit /b 0
)

echo Removendo atalho Desktop...
set "DESK=%USERPROFILE%\Desktop\Transkriptor.lnk"
if exist "%DESK%" del /f /q "%DESK%"
set "DESK2=%USERPROFILE%\OneDrive\Desktop\Transkriptor.lnk"
if exist "%DESK2%" del /f /q "%DESK2%"

echo Removendo Startup...
set "ST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\transkriptor.lnk"
if exist "%ST%" del /f /q "%ST%"

echo Removendo .venv...
if exist ".venv" rmdir /s /q ".venv"

echo.
set /p DADOS=Apagar tambem transcricoes, audio, vozes e config_user.json? (S/N, padrao N): 
if /I "%DADOS%"=="S" (
  echo Removendo dados do usuario...
  if exist "transcricoes" rmdir /s /q "transcricoes"
  if exist "_modelo_voz" rmdir /s /q "_modelo_voz"
  if exist "config_user.json" del /f /q "config_user.json"
) else (
  echo Dados do usuario preservados.
)

echo.
echo Desinstalacao concluida.
pause
