# -*- coding: utf-8 -*-
"""Integração do detector com as ações do app de bandeja (v1.2.1)."""
import threading
from unittest.mock import Mock

from detector_meet import DetectorMeet
from deteccao_reuniao import Sinal
from monitor_reuniao import texto_heartbeat


def _app_controlado(modulo):
    app = modulo.AppTranskriptor.__new__(modulo.AppTranskriptor)
    app._recusa_reuniao_ativa = False
    app._consentimento_em_andamento = False
    app._lock = threading.Lock()
    app._iniciar_transcricao = Mock()
    app._pedir_e_iniciar = Mock()
    app._parar_transcricao = Mock()
    app._status = Mock()
    # Iniciar/parar rodam fora da thread do monitor (FR-9.6); aqui executamos
    # em linha para o teste ser determinístico.
    app._em_thread = lambda alvo, _nome: alvo()
    return app


def test_titulo_real_solicita_consentimento_uma_vez(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    detector = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    titulos = ["Daily - Google Meet - Google Chrome"]

    app._processar_mudanca_meet(detector.verificar(titulos))
    app._processar_mudanca_meet(detector.verificar(titulos))
    app._processar_mudanca_meet(detector.verificar(titulos))

    app._pedir_e_iniciar.assert_called_once_with()
    app._iniciar_transcricao.assert_not_called()


def test_fim_do_meet_para_transcricao_apos_debounce(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    detector = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    meet = ["Daily - Google Meet - Google Chrome"]
    for _ in range(2):
        app._processar_mudanca_meet(detector.verificar(meet))
    for _ in range(3):
        app._processar_mudanca_meet(detector.verificar([]))

    app._parar_transcricao.assert_called_once_with()
    # v1.4: a mensagem fala em "reunião" porque o detector cobre Meet e Zoom.
    app._status.assert_called_with("Reunião encerrada. Finalizando transcricao...")


def test_fim_detectado_nao_pode_ser_ignorado(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    app._processar_mudanca_meet("encerrou")

    app._parar_transcricao.assert_called_once_with()


def test_heartbeat_distingue_fontes_fortes_de_auxiliares():
    detector = Mock()
    detector.reuniao_ativa = True
    detector.ultimos_sinais = [
        Sinal("titulo", False, forte=True),
        Sinal("microfone", True, forte=False),
        Sinal("extensao", True, forte=True),
    ]

    texto = texto_heartbeat(detector, gravando=True, ciclos=42)

    assert "fortes=[extensao]" in texto
    assert "auxiliares=[microfone]" in texto
