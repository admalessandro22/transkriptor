# -*- coding: utf-8 -*-
"""FR-10.B3 — uma pergunta por reunião, sem emperrar para sempre.

O portão `_consentimento_em_andamento` garante que uma reunião não gere duas
caixas de diálogo. Em 2026-08-07 a thread que respondia a pergunta travou e o
`finally` que reabre o portão nunca rodou: dali em diante nenhuma reunião era
sequer perguntada, mesmo depois de o app voltar a si.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from config import LIMITE_PORTAO_CONSENTIMENTO_SEG
from transkriptor_acoes import portao_consentimento_liberado

LIMITE = LIMITE_PORTAO_CONSENTIMENTO_SEG


def test_portao_fechado_bloqueia_segunda_pergunta():
    assert portao_consentimento_liberado(True, 100.0, 100.0 + LIMITE - 1, LIMITE) is False


def test_portao_aberto_deixa_perguntar():
    assert portao_consentimento_liberado(False, None, 0.0, LIMITE) is True


def test_portao_expira_e_reabre():
    assert portao_consentimento_liberado(True, 100.0, 100.0 + LIMITE, LIMITE) is True


def test_portao_sem_instante_permanece_fechado():
    """Sem saber quando abriu, o seguro é não perguntar de novo agora."""
    assert portao_consentimento_liberado(True, None, 999.0, LIMITE) is False


def test_limite_e_maior_que_o_timeout_do_dialogo():
    """O portão não pode expirar enquanto a caixa ainda está na tela."""
    from config import TIMEOUT_AVISO_GRAVACAO_SEG

    assert LIMITE > TIMEOUT_AVISO_GRAVACAO_SEG


@pytest.fixture
def app(modulo_transkriptor, monkeypatch):
    import app_ciclo_reuniao

    app = modulo_transkriptor.AppTranskriptor.__new__(
        modulo_transkriptor.AppTranskriptor
    )
    app._lock = __import__("threading").RLock()
    app._recusa_reuniao_ativa = False
    app._consentimento_em_andamento = False
    app._consentimento_aberto_em = None
    app._status = MagicMock()
    app.deteccao_ativa = True
    app.detector = SimpleNamespace(reuniao_ativa=True)
    app.chamadas = []
    app._em_thread = lambda alvo, nome: app.chamadas.append(nome)
    monkeypatch.setattr(app_ciclo_reuniao, "notificar", lambda *a, **k: None)
    return app


def test_reuniao_nao_gera_duas_perguntas(app):
    app._processar_mudanca_meet("iniciou")
    app._processar_mudanca_meet("iniciou")

    assert len(app.chamadas) == 1


def test_portao_travado_nao_cega_as_reunioes_seguintes(app, monkeypatch):
    """Regressão: o portão ficou preso e o app parou de perguntar para sempre."""
    import app_ciclo_reuniao

    relogio = {"agora": 1000.0}
    monkeypatch.setattr(app_ciclo_reuniao.time, "monotonic", lambda: relogio["agora"])

    app._processar_mudanca_meet("iniciou")
    assert len(app.chamadas) == 1

    # a thread do consentimento morreu: o finally nunca reabriu o portão
    relogio["agora"] += LIMITE + 1
    app._processar_mudanca_meet("iniciou")

    assert len(app.chamadas) == 2
