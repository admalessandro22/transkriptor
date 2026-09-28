# -*- coding: utf-8 -*-
"""T-13.E3 — payload tipado, limites e erros 4xx (nunca 500)."""
from __future__ import annotations

import pytest

from assistente_validacao import (
    PayloadInvalido,
    hosts_locais_aceitos,
    origem_exata_assistente,
    validar_chat_payload,
)


def _base(**kwargs):
    dados = {
        "modelo": "llama3",
        "transcricao": "reuniao.txt",
        "pergunta": "o que foi decidido?",
        "historico": [{"role": "user", "content": "oi"}],
    }
    dados.update(kwargs)
    return dados


def test_rejeita_nao_objeto():
    for corpo in ([], [1], "texto", 42, None, True):
        with pytest.raises(PayloadInvalido):
            validar_chat_payload(corpo)


def test_rejeita_item_nao_objeto():
    for historico in ([["x"]], [[42]], [{"role": "admin", "content": "x"}],
                      [{"role": "user"}], [{"role": "user", "content": ""}],
                      [{"role": "user", "content": "x" * 5000}]):
        with pytest.raises(PayloadInvalido):
            validar_chat_payload(_base(historico=historico))


def test_rejeita_strings_fora_do_limite():
    with pytest.raises(PayloadInvalido):
        validar_chat_payload(_base(modelo="m" * 200))
    with pytest.raises(PayloadInvalido):
        validar_chat_payload(_base(pergunta="p" * 5000))
    with pytest.raises(PayloadInvalido):
        validar_chat_payload(_base(transcricao="../x"))
    with pytest.raises(PayloadInvalido):
        validar_chat_payload(_base(historico=[{"role": "user", "content": "x"}] * 21))


def test_aceita_payload_valido():
    pedido = validar_chat_payload(_base())
    assert pedido["modelo"] == "llama3"
    assert pedido["historico"][0].role == "user"


def test_host_local_aceito_externo_nao():
    assert hosts_locais_aceitos("127.0.0.1:5052") is True
    assert hosts_locais_aceitos("localhost:5052") is True
    assert hosts_locais_aceitos("evil.example.test") is False
    assert hosts_locais_aceitos(None) is False


def test_origem_externa_rejeitada_local_ok():
    assert origem_exata_assistente(None, "http://127.0.0.1:5052/") is False
    assert origem_exata_assistente("http://127.0.0.1:5052", "http://127.0.0.1:5052/") is True
    assert origem_exata_assistente("http://localhost:5052", "http://127.0.0.1:5052/") is False
    assert origem_exata_assistente("http://127.0.0.1:9999", "http://127.0.0.1:5052/") is False
    assert origem_exata_assistente("https://evil.example.test", "http://127.0.0.1:5052/") is False
    assert origem_exata_assistente("http://127.0.0.1.evil.test", "http://127.0.0.1:5052/") is False
