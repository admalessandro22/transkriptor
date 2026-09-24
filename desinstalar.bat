@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM --non-interactive --preserve-data --shortcut-dir <temporario>
if /I "%~1"=="--non-interactive" goto desinstalar_isolado
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
  echo Cancelado. Nenhum arquivo foi tocado.
  pause
  exit /b 0
)

echo Verificando processo em execucao...
python scripts\instalar_helper.py --check processo
if errorlevel 1 (
  echo Feche o Transkriptor e aguarde o fim da gravacao antes de desinstalar.
  pause
  exit /b 1
)

set /p DADOS=Apagar tambem transcricoes, audio, vozes e config_user.json? (S/N, padrao N): 
if /I "%DADOS%"=="S" (
  python scripts\instalar_helper.py --uninstall-normal --delete-data
) else (
  python scripts\instalar_helper.py --uninstall-normal --preserve-data
)
if errorlevel 1 (
  echo Desinstalacao interrompida. Verifique os alvos e tente novamente.
  pause
  exit /b 1
)

echo.
echo Desinstalacao concluida.
pause
exit /b 0

:desinstalar_isolado
python scripts\instalar_helper.py --isolated-uninstall %*
exit /b %ERRORLEVEL%
