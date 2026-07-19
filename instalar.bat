@echo off
chcp 65001 >nul
echo ============================================
echo   Instalando Transkriptor 1.2.1
echo ============================================
echo.

echo [1/3] Instalando PyTorch (CUDA 12.8)...
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] Falha na instalacao do PyTorch CUDA. Tentando versao CPU...
    python -m pip install torch torchaudio
)
echo.

echo [2/3] Instalando dependencias do projeto...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias. Verifique o erro acima.
    pause
    exit /b 1
)
echo.

echo [3/3] Criando atalho...
for /f "delims=" %%P in ('python scripts/resolver_pythonw.py') do set "PYTHONW=%%P"
if not defined PYTHONW (
  echo [ERRO] pythonw.exe nao encontrado.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\criar_atalho_desktop.ps1" ^
  -Pythonw "%PYTHONW%" ^
  -Aplicativo "%~dp0transkriptor.pyw" ^
  -Icone "%~dp0transkriptor.ico"
if %errorlevel% neq 0 (
  echo [ERRO] Falha ao criar o atalho Transkriptor na Area de Trabalho.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   Instalacao concluida!
echo   Use o atalho "Transkriptor" na Area de Trabalho.
echo ============================================
pause
