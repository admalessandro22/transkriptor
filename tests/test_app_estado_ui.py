# -*- coding: utf-8 -*-
"""FR-14.D1 — snapshot de estado sem lock e sem dados sensíveis (T-14.D1).

Não importa `transkriptor`: usa dublês com os mesmos atributos que a bandeja expõe.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent


def _app(**kw):
    base = dict(transcritor=None, deteccao_ativa=True, _em_erro=False, _instante_erro=None, _estado_processamento=None,
                detector=SimpleNamespace(fontes_da_reuniao=[]))
    base.update(kw)
    return SimpleNamespace(**base)


def test_snapshot_nao_pede_lock():
    arvore = ast.parse((REPO / "app_estado_ui.py").read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        assert not isinstance(no, ast.With) or not any(
            isinstance(i.context_expr, ast.Attribute) and i.context_expr.attr == "_lock" for i in no.items
        ), "app_estado_ui não pode pedir self._lock"
    fonte = (REPO / "app_estado_ui.py").read_text(encoding="utf-8")
    assert "_lock" not in fonte.replace("sem pedir `self._lock`", "").replace("self._lock` (", "")


def test_snapshot_sem_campos_sensiveis(tmp_path, monkeypatch):
    import app_estado_ui

    monkeypatch.setattr("politica_privacidade.modo_efetivo", lambda: SimpleNamespace(value="protected"))
    app = _app(transcritor=SimpleNamespace(rodando=True, diarizando=False), detector=SimpleNamespace(fontes_da_reuniao=["titulo", "microfone"]))
    dados = app_estado_ui.snapshot(app, indice=tmp_path / "indice.json").como_dict()
    assert app_estado_ui.validar_snapshot(dados) == []
    assert set(dados) == set(app_estado_ui.CAMPOS)
    assert dados["estado"] == "gravando" and dados["fontes"] == ["titulo", "microfone"]
    assert dados["protecao"] == "protected" and dados["ultima_reuniao"] is None


@pytest.mark.parametrize("cenario, esperado", [
    (dict(), ("aguardando", "Aguardando reunião")),
    (dict(deteccao_ativa=False), ("pausado", "Pausado")),
    (dict(transcritor=SimpleNamespace(rodando=True, diarizando=False)), ("gravando", "Gravando")),
    (dict(transcritor=SimpleNamespace(rodando=False, diarizando=True)), ("separando_vozes", "Separando vozes")),
    (dict(_estado_processamento="Processando"), ("processando", "Processando reunião")),
    (dict(_em_erro=True, _instante_erro=100.0), ("erro", "Erro")),
])
def test_estados_mapeiam_glossario(cenario, esperado, tmp_path):
    import app_estado_ui

    snap = app_estado_ui.snapshot(_app(**cenario), agora=110.0, indice=tmp_path / "indice.json")
    assert (snap.estado, snap.rotulo) == esperado
    if snap.estado != "gravando":
        assert snap.fontes == ()


def test_ultima_reuniao_vem_do_indice_sem_abrir_conteudo(tmp_path, monkeypatch):
    import app_estado_ui
    from indice_transcricoes import MeetingSummary

    def _listar(caminho, *, cursor, limit):
        assert limit == 1
        return [MeetingSummary("2026-09-22_10h03", None, "2026-09-22T10:03:00", 1800000, "rev-3", "pronto")], None

    monkeypatch.setattr("indice_transcricoes.listar_reunioes", _listar)
    ultima = app_estado_ui.ultima_reuniao(tmp_path / "indice.json")
    assert ultima == {"meeting_id": "2026-09-22_10h03", "started_at": "2026-09-22T10:03:00", "estado": "Pronta"}


def test_api_estado_503_sem_provedor_e_200_com(headers_token):
    import app_estado_ui
    from assistente import app

    app_estado_ui.registrar_provedor(None)
    cliente = app.test_client()
    resposta = cliente.get("/api/estado", headers=headers_token)
    assert resposta.status_code == 503 and "indisponível" in resposta.get_json()["erro"]
    try:
        app_estado_ui.registrar_provedor(lambda: app_estado_ui.snapshot(_app(deteccao_ativa=False)))
        resposta = cliente.get("/api/estado", headers=headers_token)
        assert resposta.status_code == 200
        dados = resposta.get_json()
        assert dados["estado"] == "pausado" and app_estado_ui.validar_snapshot(dados) == []
        assert "Cache-Control" in resposta.headers
    finally:
        app_estado_ui.registrar_provedor(None)


def test_api_estado_exige_token():
    from assistente import app

    assert app.test_client().get("/api/estado").status_code == 403
