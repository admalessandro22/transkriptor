# -*- coding: utf-8 -*-
"""Sala do Meet vinculada depois do início da gravação (spec v1.8, emenda 22/09/2026).

"se houver zero ou mais de um [código ativo], a sessão não recebe nomes da
extensão até existir vínculo inequívoco" — o vínculo pode chegar depois.
Regressão 24/09/2026: gravação começou sem hint único e a reunião inteira
selou 0 eventos do Meet.
"""
from __future__ import annotations

import logging

import pytest

from meet_bridge import MeetBridge
from sessao_reuniao import EnvelopeRejeitado, criar_sessao


def _hello(bridge, conexao, aba, sala, ativa=True):
    bridge.registrar_hello({"tipo": "hello", "connection_id": conexao, "tab_id": aba, "meeting_hint": sala, "active": ativa})


def _sessao_sem_sala(bridge, tmp_path):
    from eventos_meet_store import EventStore

    sessao = criar_sessao("chave-opaca", "2026-09-19T20:00:00Z", "padrao")
    bridge.definir_sessao_ativa(sessao, EventStore(tmp_path / "eventos", sessao), meeting_hint=bridge.hint_ativo_unico())
    return sessao


def test_extensao_que_chega_depois_vincula_a_sala(chave_teste, tmp_path):
    bridge = MeetBridge()
    sessao = _sessao_sem_sala(bridge, tmp_path)  # nenhuma aba ativa no início
    _hello(bridge, "c1", "aba-1", "abc-defg-hij")
    resposta = bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    assert resposta["session_id"] == sessao.session_id
    # vínculo feito: outra sala continua recusada, mesmo que vire a única ativa
    _hello(bridge, "c1", "aba-1", "abc-defg-hij", ativa=False)
    _hello(bridge, "c2", "aba-2", "xyz-abcd-efg")
    with pytest.raises(EnvelopeRejeitado):
        bridge.iniciar_conexao_logica("c2", "aba-2", 1_789_848_060_000, meeting_hint="xyz-abcd-efg")


def test_duas_salas_ativas_continuam_sem_vinculo(chave_teste, tmp_path):
    bridge = MeetBridge()
    _sessao_sem_sala(bridge, tmp_path)
    _hello(bridge, "c1", "aba-1", "abc-defg-hij")
    _hello(bridge, "c2", "aba-2", "xyz-abcd-efg")
    with pytest.raises(EnvelopeRejeitado):
        bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")


def test_sem_sessao_nao_vincula(chave_teste):
    bridge = MeetBridge()
    _hello(bridge, "c1", "aba-1", "abc-defg-hij")
    with pytest.raises(EnvelopeRejeitado):
        bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")


def test_vinculo_e_recusa_aparecem_no_log_sem_codigo_da_sala(chave_teste, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="meet_bridge")
    bridge = MeetBridge()
    _sessao_sem_sala(bridge, tmp_path)
    _hello(bridge, "c1", "aba-1", "abc-defg-hij")
    bridge.iniciar_conexao_logica("c1", "aba-1", 1_789_848_060_000, meeting_hint="abc-defg-hij")
    texto = caplog.text
    assert "sem sala do Meet vinculada" in texto
    assert "Sala do Meet vinculada" in texto
    assert "abc-defg-hij" not in texto
