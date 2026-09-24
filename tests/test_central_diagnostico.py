# -*- coding: utf-8 -*-
"""FR-14.D3 — diagnóstico e retranscrição pela Central (T-14.D3)."""
from __future__ import annotations

import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from assistente import COOKIE_TOKEN, HEADER_TOKEN, app, obter_token_sessao

ITENS = [
    {"nome": "numpy", "estado": "OK", "detalhe": "2.1.0"},
    {"nome": "Microfone", "estado": "ERRO", "detalhe": r"nenhum dispositivo em C:\Users\pessoa\AppData"},
]


@pytest.fixture()
def bandeja(monkeypatch, tmp_path):
    import central_config
    import central_diagnostico

    falso = SimpleNamespace(detector=None, modelo_whisper="auto", capturar_mic=True, transcritor=None,
                            diarizacao_ativa=True, criptografar_transcricoes=True, identificar_minha_voz=False,
                            _gravando=lambda: False, _status=lambda m: falso.mensagens.append(m), mensagens=[])
    central_config.registrar_app(falso)
    central_diagnostico._ULTIMOS_ITENS.clear()
    monkeypatch.setattr("diagnostico.coletar", lambda **_k: list(ITENS))
    monkeypatch.setattr("diagnostico.salvar_relatorio", lambda texto, pasta=None: str(tmp_path / "diagnostico_teste.txt"))
    yield falso
    central_config.registrar_app(None)


@pytest.fixture()
def cliente():
    app.config["TESTING"] = True
    return app.test_client()


def _h():
    return {HEADER_TOKEN: obter_token_sessao()}


def test_diagnostico_503_sem_bandeja(cliente):
    import central_config

    central_config.registrar_app(None)
    assert cliente.post("/api/diagnostico", json={}, headers=_h()).status_code == 503
    assert cliente.post("/api/acoes/retranscrever", json={"nome": "x.wav"}, headers=_h()).status_code == 503


def test_diagnostico_devolve_itens_resumo_e_relatorio(cliente, bandeja):
    resposta = cliente.post("/api/diagnostico", json={}, headers=_h())
    assert resposta.status_code == 200, resposta.get_json()
    corpo = resposta.get_json()
    assert [i["nome"] for i in corpo["itens"]] == ["numpy", "Microfone"]
    assert corpo["erros"] == 1 and corpo["avisos"] == 0
    assert corpo["relatorio"] == "diagnostico_teste.txt" and "\\" not in corpo["relatorio"]


def test_diagnostico_exportar_sem_pii(cliente, bandeja, monkeypatch):
    monkeypatch.setenv("USERPROFILE", r"C:\Users\pessoa")
    assert cliente.get("/api/diagnostico/exportar", headers=_h()).status_code == 404
    cliente.post("/api/diagnostico", json={}, headers=_h())
    resposta = cliente.get("/api/diagnostico/exportar", headers=_h())
    assert resposta.status_code == 200
    texto = resposta.get_data(as_text=True)
    assert "Users" not in texto and "<pasta-pessoal>" in texto
    assert "attachment" in resposta.headers["Content-Disposition"]


def test_retranscrever_exige_header_e_nome_da_lista(cliente, bandeja, monkeypatch):
    itens = [{"nome": "2026-09-22.wav", "caminho": r"C:\x\2026-09-22.wav", "mtime": datetime.datetime(2026, 9, 22, 10, 3), "duracao_seg": 61.0, "rotulo": "x"}]
    monkeypatch.setattr("retranscritor.listar_audios", lambda pasta=None: itens)
    cliente.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    assert cliente.post("/api/acoes/retranscrever", json={"nome": "2026-09-22.wav"}).status_code == 403
    assert cliente.post("/api/acoes/retranscrever", json={"nome": "../outro.wav"}, headers=_h()).status_code == 400
    lista = cliente.get("/api/audios-retidos", headers=_h()).get_json()
    assert lista == [{"nome": "2026-09-22.wav", "mtime": "2026-09-22T10:03", "duracao_seg": 61.0}]
    assert "caminho" not in lista[0]


def test_retranscrever_inicia_job_com_preferencias_da_bandeja(cliente, bandeja, monkeypatch):
    import central_diagnostico

    itens = [{"nome": "a.wav", "caminho": r"C:\x\a.wav", "mtime": datetime.datetime(2026, 9, 22, 10, 3), "duracao_seg": 5.0, "rotulo": "a"}]
    chamadas = []
    monkeypatch.setattr("retranscritor.listar_audios", lambda pasta=None: itens)
    monkeypatch.setattr("retranscritor.retranscrever", lambda caminho, **kw: chamadas.append((caminho, kw)) or "saida.txt")
    resposta = cliente.post("/api/acoes/retranscrever", json={"nome": "a.wav"}, headers=_h())
    assert resposta.status_code == 202 and resposta.get_json()["aceito"] is True
    import time

    for _ in range(50):
        if chamadas and not central_diagnostico._RETRANSCRICAO["em_curso"]:
            break
        time.sleep(0.05)
    assert chamadas and chamadas[0][0] == r"C:\x\a.wav"
    assert chamadas[0][1]["diarizar"] is True and chamadas[0][1]["criptografar"] is True
    assert "Retranscrição concluída." in bandeja.mensagens


def test_dialogo_tk_de_retranscrever_removido():
    fonte = Path(__file__).resolve().parent.parent
    flows = (fonte / "transkriptor_menu_flows.py").read_text(encoding="utf-8")
    assert "tkinter" not in flows and "simpledialog" not in flows and "_escolher_audio_dialog" not in flows
    for nome in fonte.glob("*.py"):
        assert "import tkinter" not in nome.read_text(encoding="utf-8"), nome.name


class _PareadorFalso:
    def __init__(self):
        self.emitidos = 0

    def gerar_convite(self):
        self.emitidos += 1
        return f"pair-sintetico-{self.emitidos:04d}-0000000000"


def test_pareamento_emite_convite_de_uso_unico(cliente, bandeja):
    """Gap da integração: o convite existia no arranque, mas nunca era mostrado."""
    bandeja.meet_bridge = SimpleNamespace(pareador=_PareadorFalso())
    bandeja.usar_nomes_meet = True
    resposta = cliente.post("/api/acoes/pareamento", json={}, headers=_h())
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["codigo"].startswith("pair-") and corpo["validade_seg"] >= 60 and corpo["ponte_ativa"] is True
    assert bandeja.convite_pareamento_meet == corpo["codigo"]
    segundo = cliente.post("/api/acoes/pareamento", json={}, headers=_h()).get_json()
    assert segundo["codigo"] != corpo["codigo"]
    assert bandeja.meet_bridge.pareador.emitidos == 2


def test_pareamento_exige_token_e_ponte(cliente, bandeja):
    cliente.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    assert cliente.post("/api/acoes/pareamento", json={}).status_code == 403
    resposta = cliente.post("/api/acoes/pareamento", json={}, headers=_h())
    assert resposta.status_code == 503
    assert "Identificar nomes do Meet" in resposta.get_json()["erro"]
