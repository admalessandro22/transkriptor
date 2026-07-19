# -*- coding: utf-8 -*-
"""Testes do atalho Windows do Transkriptor (v1.2.1)."""
import json
import os
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "criar_atalho_desktop.ps1"


def _inspecionar_atalho(caminho):
    env = os.environ.copy()
    env["TRANSKRIPTOR_ATALHO_TESTE"] = str(caminho)
    codigo = r"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TRANSKRIPTOR_ATALHO_TESTE)
[pscustomobject]@{
  TargetPath = $s.TargetPath
  Arguments = $s.Arguments
  WorkingDirectory = $s.WorkingDirectory
  IconLocation = $s.IconLocation
  WindowStyle = $s.WindowStyle
} | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", codigo],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def test_cria_atalho_com_metadados_e_caminhos_com_espacos(tmp_path):
    pasta = tmp_path / "instalacao com espacos"
    pasta.mkdir()
    pythonw = pasta / "pythonw.exe"
    aplicativo = pasta / "transkriptor.pyw"
    icone = pasta / "transkriptor.ico"
    for caminho in (pythonw, aplicativo, icone):
        caminho.write_bytes(b"teste")
    destino = tmp_path / "Desktop de teste" / "Transkriptor.lnk"

    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(SCRIPT),
            "-Pythonw", str(pythonw),
            "-Aplicativo", str(aplicativo),
            "-Icone", str(icone),
            "-Destino", str(destino),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert destino.is_file()
    dados = _inspecionar_atalho(destino)
    assert Path(dados["TargetPath"]).resolve() == pythonw.resolve()
    assert dados["Arguments"] == f'"{aplicativo.resolve()}"'
    assert Path(dados["WorkingDirectory"]).resolve() == pasta.resolve()
    assert str(icone.resolve()).lower() in dados["IconLocation"].lower()
    assert dados["WindowStyle"] == 7


def test_instalador_usa_script_unico_e_nao_cria_atalho_redundante():
    texto = (REPO / "instalar.bat").read_text(encoding="utf-8")
    assert r"scripts\criar_atalho_desktop.ps1" in texto
    assert "if %errorlevel% neq 0" in texto.lower()
    assert "Iniciar Transkriptor.lnk" not in texto
    assert "$ws.CreateShortcut" not in texto
