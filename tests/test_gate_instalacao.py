# -*- coding: utf-8 -*-
"""T-13.G2 — instalação isolada e escopo de remoção verificável."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_gate_recusa_raiz_real_do_checkout():
    from scripts.gate_instalacao import validar_raiz_gate

    with pytest.raises(ValueError, match="raiz temporária"):
        validar_raiz_gate(REPO)


def test_gate_preserva_dados_sinteticos_ao_desinstalar(tmp_path, monkeypatch):
    from scripts.instalar_helper import desinstalar_isolado
    from scripts.gate_instalacao import validar_raiz_gate

    raiz = validar_raiz_gate(tmp_path / "Pasta Com Acento çã")
    raiz.mkdir()
    nonce = "0123456789abcdef0123456789abcdef"
    monkeypatch.setenv("TRANSKRIPTOR_GATE_NONCE", nonce)
    (raiz / ".transkriptor-gate.json").write_text(
        json.dumps({"root": str(raiz), "nonce": nonce}), encoding="utf-8")
    (raiz / ".venv" / "Scripts").mkdir(parents=True)
    (raiz / ".venv" / "Scripts" / "python.exe").write_bytes(b"fake")
    dados = raiz / "transcricoes" / "canario.bin"
    dados.parent.mkdir()
    dados.write_bytes(b"dados-sinteticos")
    antes = hashlib.sha256(dados.read_bytes()).hexdigest()
    atalho = raiz / "atalhos" / "Transkriptor.lnk"
    atalho.parent.mkdir()
    atalho.write_bytes(b"atalho-sintetico")
    desinstalar_isolado(raiz, raiz / "atalhos")
    assert not (raiz / ".venv").exists()
    assert not atalho.exists()
    assert hashlib.sha256(dados.read_bytes()).hexdigest() == antes


def test_desinstalacao_normal_limita_alvos_e_preserva_dados(tmp_path, monkeypatch):
    from scripts import instalar_helper

    raiz = tmp_path / "checkout"
    raiz.mkdir()
    perfil = tmp_path / "perfil"
    appdata = tmp_path / "appdata"
    monkeypatch.setenv("USERPROFILE", str(perfil))
    monkeypatch.setenv("APPDATA", str(appdata))
    (raiz / ".venv").mkdir()
    (raiz / ".venv" / "python.exe").write_bytes(b"venv")
    dado = raiz / "transcricoes" / "canario.txt"
    dado.parent.mkdir()
    dado.write_bytes(b"privado")
    atalho = perfil / "Desktop" / "Transkriptor.lnk"
    atalho.parent.mkdir(parents=True)
    atalho.write_bytes(b"atalho")
    outro = perfil / "Desktop" / "outro.lnk"
    outro.write_bytes(b"outro")
    monkeypatch.setattr(instalar_helper, "processo_ativo", lambda: False)
    monkeypatch.setattr(instalar_helper, "atalho_deste_checkout", lambda caminho, base: caminho == atalho and base == raiz.resolve())

    instalar_helper.desinstalar_normal(raiz, apagar_dados=False)
    assert not (raiz / ".venv").exists()
    assert not atalho.exists()
    assert dado.read_bytes() == b"privado"
    assert outro.read_bytes() == b"outro"


def test_desinstalacao_normal_preserva_atalho_de_outra_instalacao(tmp_path, monkeypatch):
    from scripts import instalar_helper

    raiz = tmp_path / "checkout"
    raiz.mkdir()
    perfil = tmp_path / "perfil"
    monkeypatch.setenv("USERPROFILE", str(perfil))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    atalho = perfil / "Desktop" / "Transkriptor.lnk"
    atalho.parent.mkdir(parents=True)
    atalho.write_bytes(b"outra-instalacao")
    monkeypatch.setattr(instalar_helper, "processo_ativo", lambda: False)
    monkeypatch.setattr(instalar_helper, "atalho_deste_checkout", lambda caminho, base: False)

    instalar_helper.desinstalar_normal(raiz)
    assert atalho.read_bytes() == b"outra-instalacao"


def test_atalho_real_e_reconhecido_somente_pelo_checkout_correto(tmp_path):
    from scripts.instalar_helper import atalho_deste_checkout

    raiz = tmp_path / "instalacao com espacos"
    pythonw = raiz / ".venv" / "Scripts" / "pythonw.exe"
    pythonw.parent.mkdir(parents=True)
    aplicativo = raiz / "transkriptor.pyw"
    icone = raiz / "transkriptor.ico"
    for caminho in (pythonw, aplicativo, icone):
        caminho.write_bytes(b"teste")
    atalho = tmp_path / "Desktop falso" / "Transkriptor.lnk"
    subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(REPO / "scripts" / "criar_atalho_desktop.ps1"),
        "-Pythonw", str(pythonw), "-Aplicativo", str(aplicativo),
        "-Icone", str(icone), "-Destino", str(atalho),
    ], check=True, capture_output=True, text=True)
    assert atalho_deste_checkout(atalho, raiz)
    assert not atalho_deste_checkout(atalho, tmp_path / "outra copia")


def test_desinstalacao_isolada_exige_marcador_do_gate(tmp_path):
    from scripts.instalar_helper import desinstalar_isolado

    raiz = tmp_path / "copia"
    (raiz / ".venv").mkdir(parents=True)
    with pytest.raises(ValueError, match="marcador"):
        desinstalar_isolado(raiz, raiz / "atalhos")
    assert (raiz / ".venv").exists()


def test_desinstalacao_normal_bloqueia_processo_ativo(tmp_path, monkeypatch):
    from scripts import instalar_helper

    raiz = tmp_path / "checkout"
    (raiz / ".venv").mkdir(parents=True)
    monkeypatch.setattr(instalar_helper, "processo_ativo", lambda: True)
    with pytest.raises(RuntimeError, match="execução"):
        instalar_helper.desinstalar_normal(raiz, apagar_dados=False)
    assert (raiz / ".venv").exists()


def test_exclusao_de_dados_so_atinge_alvos_explicitos(tmp_path, monkeypatch):
    from scripts import instalar_helper

    raiz = tmp_path / "checkout"
    raiz.mkdir()
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "perfil"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(instalar_helper, "processo_ativo", lambda: False)
    for nome in ("transcricoes", "audio", "_modelo_voz"):
        (raiz / nome).mkdir()
        (raiz / nome / "canario").write_bytes(b"dado")
    (raiz / "config_user.json").write_text("{}", encoding="utf-8")
    vizinho = raiz / "nao_apagar"
    vizinho.mkdir()
    (vizinho / "canario").write_bytes(b"manter")
    instalar_helper.desinstalar_normal(raiz, apagar_dados=True)
    assert all(not (raiz / nome).exists() for nome in
               ("transcricoes", "audio", "_modelo_voz", "config_user.json"))
    assert (vizinho / "canario").read_bytes() == b"manter"


def test_batches_expoem_flags_seguras_sem_apagar_dados():
    instalar = (REPO / "instalar.bat").read_text(encoding="utf-8")
    desinstalar = (REPO / "desinstalar.bat").read_text(encoding="utf-8")
    assert "--non-interactive" in instalar and "--skip-warmup" in instalar
    assert "--shortcut-dir" in instalar
    assert instalar.count("'\"\"%VENV_PY%\"") == 2
    assert "--non-interactive" in desinstalar and "--preserve-data" in desinstalar
    assert "--shortcut-dir" in desinstalar
    for nome in ("instalar.bat", "desinstalar.bat"):
        bruto = (REPO / nome).read_bytes()
        assert b"\r\n" in bruto and bruto.count(b"\r\n") == bruto.count(b"\n")
    assert "rmdir" not in desinstalar.lower()
    assert "del /f" not in desinstalar.lower()
    assert "--uninstall-normal" in desinstalar


def test_for_f_le_versao_com_python_em_caminho_com_espacos(tmp_path):
    batch = tmp_path / "versao.bat"
    batch.write_bytes((
        '@echo off\r\n'
        f'set "VENV_PY={sys.executable}"\r\n'
        'for /f "delims=" %%V in (\'""%VENV_PY%" scripts\\instalar_helper.py --version"\') do echo VERSAO=%%V\r\n'
    ).encode("utf-8"))
    resultado = subprocess.run(["cmd", "/d", "/c", str(batch)], cwd=REPO,
                               capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
    import config
    assert f"VERSAO={config.VERSAO}" in resultado.stdout
    assert "não é reconhecido" not in resultado.stdout


def test_cli_isolado_exige_flags_e_encaminha_atalho_temporario(tmp_path, monkeypatch):
    from scripts import instalar_helper

    chamadas = []
    monkeypatch.setattr(
        instalar_helper, "instalar_isolado",
        lambda raiz, rota, atalho: chamadas.append((Path(raiz), rota, Path(atalho))),
    )
    atalho = tmp_path / "Desktop falso"
    assert instalar_helper.main([
        "--isolated-install", "--non-interactive", "--route", "cpu",
        "--skip-warmup", "--shortcut-dir", str(atalho),
    ]) == 0
    assert chamadas == [(REPO, "cpu", atalho)]


def test_gate_copia_somente_versionados():
    from scripts.gate_instalacao import arquivos_versionados

    nomes = arquivos_versionados(REPO)
    assert Path("requirements/requirements-cpu.lock") in nomes
    assert Path("instalar.bat") in nomes
    assert all("transcricoes" not in p.parts and ".venv" not in p.parts for p in nomes)


def test_gate_prova_duas_partidas_uma_instancia(tmp_path):
    from scripts.gate_instalacao import provar_instancia

    resultado = provar_instancia(tmp_path, Path(sys.executable))
    assert resultado["instancias_primeiro_start"] == 1
    assert resultado["instancias_segundo_start"] == 1
    assert resultado["pid_filho"] > 0
    assert resultado["porta"] > 0
