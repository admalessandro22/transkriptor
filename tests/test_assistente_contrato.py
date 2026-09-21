# -*- coding: utf-8 -*-
"""T-13.F1 — contrato de conversa por reunião (meeting_id + geração)."""
from __future__ import annotations

import pytest

from assistente_validacao import PayloadInvalido, validar_chat_request


def _base(**kwargs):
    dados = {
        "modelo": "llama3",
        "transcricao": "a.txt",
        "pergunta": "resuma",
        "historico": [],
    }
    dados.update(kwargs)
    return dados


def test_herda_transcricao_sem_meeting_id():
    pedido = validar_chat_request(_base())
    assert pedido.meeting_id == "a.txt"
    assert len(pedido.generation_id) > 0


def test_janela_corta_antigas_sem_rejeitar():
    historico = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
        for i in range(24)
    ]
    pedido = validar_chat_request(_base(meeting_id="a", historico=historico))
    assert len(pedido.history) == 20
    assert pedido.history[-1].content == "m23"
    assert pedido.history[0].content == "m4"


def test_meeting_id_com_path_reprova():
    with pytest.raises(PayloadInvalido):
        validar_chat_request(_base(meeting_id="../x"))


def test_generation_invalida_reprova():
    with pytest.raises(PayloadInvalido):
        validar_chat_request(_base(meeting_id="a", generation_id=""))
    with pytest.raises(PayloadInvalido):
        validar_chat_request(_base(meeting_id="a", generation_id="g" * 81))


def test_revisao_limite():
    pedido = validar_chat_request(_base(meeting_id="a", transcript_revision="2026@12"))
    assert pedido.transcript_revision == "2026@12"
    with pytest.raises(PayloadInvalido):
        validar_chat_request(_base(meeting_id="a", transcript_revision="r" * 121))
