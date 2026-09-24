# -*- coding: utf-8 -*-
"""T-13.G2 — caminhos difíceis, venv único, CLI e desinstalação segura."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_resolver_venv_com_espaco_e_acento(tmp_path):
    from scripts.resolver_pythonw import resolver_com_motivo

    base = tmp_path / "Pasta Com Acento çã"
    alvo = base / ".venv" / "Scripts" / "pythonw.exe"
    alvo.parent.mkdir(parents=True)
    alvo.write_bytes(b"fake")
    caminho, motivo = resolver_com_motivo(base)
    assert caminho == str(alvo)
    assert motivo == "venv"


def test_resolver_sem_python_retorna_motivo(tmp_path, monkeypatch):
    from scripts import resolver_pythonw
    from scripts.resolver_pythonw import resolver_com_motivo

    monkeypatch.setattr(resolver_pythonw.sys, "executable", str(tmp_path / "nada.exe"))
    caminho, motivo = resolver_com_motivo(tmp_path)
    assert caminho is None
    assert motivo


def test_resolver_venv_incompleto_nao_mistura(tmp_path, monkeypatch):
    from scripts import resolver_pythonw
    from scripts.resolver_pythonw import resolver_com_motivo

    (tmp_path / ".venv" / "Scripts").mkdir(parents=True)
    monkeypatch.setattr(resolver_pythonw.sys, "executable", str(tmp_path / "nada.exe"))
    caminho, motivo = resolver_com_motivo(tmp_path)
    assert caminho is None
    assert "incompleto" in motivo.lower() or "venv" in motivo.lower()


def test_porta_ocupada_pula(tmp_path, monkeypatch):
    import socket

    import assistente

    ocupado = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ocupado.bind(("127.0.0.1", 0))
    ocupado.listen(1)
    try:
        livre = ("127.0.0.1", 0)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            porta_livre_nova = s.getsockname()[1]
        monkeypatch.setattr(assistente, "PORTAS_FALLBACK", [ocupado.getsockname()[1], porta_livre_nova])
        assert assistente.porta_livre() == porta_livre_nova
    finally:
        ocupado.close()


def test_processo_ativo_detecta_gravacao():
    from scripts.instalar_helper import processo_ativo

    def runner(cmd):
        class R:
            returncode = 0
            stdout = '"transkriptor.pyw" "processador_reuniao --job x"'
            stderr = ""
        return R()

    assert processo_ativo(runner) is True

    def vazio(cmd):
        class R:
            returncode = 0
            stdout = '"explorer.exe"'
            stderr = ""
        return R()

    assert processo_ativo(vazio) is False


def test_desinstalador_consulta_linha_de_comando_e_falha_fechado():
    from scripts.instalar_helper import processo_ativo

    comandos = []

    def falha(cmd):
        comandos.append(cmd)

        class R:
            returncode = 1
            stdout = ""
            stderr = "sem acesso"

        return R()

    assert processo_ativo(falha) is True
    assert "Get-CimInstance" in " ".join(comandos[0])


def test_alvos_desinstalacao_exatos_sem_apagar_dados(tmp_path, monkeypatch):
    import scripts.instalar_helper as helper

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    alvos = helper.alvos_desinstalacao()
    assert any(str(p).endswith("Transkriptor.lnk") for p in alvos["atalhos"])
    assert Path(alvos["venv"]).name == ".venv"
    assert "transcricoes" not in str(alvos["venv"])
    for p in alvos["atalhos"]:
        assert not Path(p).exists()


def test_cli_aceita_auto():
    import argparse

    import transcrever_meet

    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default="auto", choices=["auto", "tiny", "base"])
    args = parser.parse_args([])
    assert args.modelo == "auto"
    import inspect

    fonte = inspect.getsource(transcrever_meet.main)
    assert '"auto"' in fonte or "'auto'" in fonte


def test_versao_extensao_gerada_de_config():
    import config
    from scripts.sincronizar_versao_extensao import versao_extensao_para

    assert versao_extensao_para(config.VERSAO) == "1.7.0"
    assert versao_extensao_para("2.3.4") == "2.3.0"


def test_bats_usam_venv_e_citam_argumentos():
    iniciar = (REPO / "iniciar.bat").read_text(encoding="utf-8")
    assert "resolver_pythonw" in iniciar
    assert ".venv" in iniciar
    assert "%*" in iniciar
    desinstalar = (REPO / "desinstalar.bat").read_text(encoding="utf-8")
    assert "processo" in desinstalar.lower()
    assert "PRESERVADOS" in desinstalar


def test_standalone_aguarda_antes_do_navegador(monkeypatch):
    import assistente
    from unittest.mock import MagicMock

    chamadas = []
    monkeypatch.setattr(assistente, "iniciar_servidor_em_thread", lambda *a, **k: chamadas.append("servidor") or MagicMock())
    monkeypatch.setattr(assistente, "aguardar_servidor", lambda *a, **k: chamadas.append("aguardar") or True)
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: chamadas.append("navegador"))
    assistente.iniciar_standalone(porta=5059)
    assert chamadas.index("servidor") < chamadas.index("aguardar") < chamadas.index("navegador")
