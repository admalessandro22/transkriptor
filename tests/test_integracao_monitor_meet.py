# -*- coding: utf-8 -*-
"""Integração do detector com as ações do app de bandeja (v1.2.1)."""
from unittest.mock import Mock

from detector_meet import DetectorMeet


def _app_controlado(modulo, manual=False):
    app = modulo.AppTranskriptor.__new__(modulo.AppTranskriptor)
    app._modo_manual = manual
    app._iniciar_transcricao = Mock()
    app._parar_transcricao = Mock()
    app._status = Mock()
    return app


def test_titulo_real_inicia_transcricao_uma_vez(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    detector = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    titulos = ["Daily - Google Meet - Google Chrome"]

    app._processar_mudanca_meet(detector.verificar(titulos))
    app._processar_mudanca_meet(detector.verificar(titulos))
    app._processar_mudanca_meet(detector.verificar(titulos))

    app._iniciar_transcricao.assert_called_once_with()


def test_fim_do_meet_para_transcricao_apos_debounce(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    detector = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    meet = ["Daily - Google Meet - Google Chrome"]
    for _ in range(2):
        app._processar_mudanca_meet(detector.verificar(meet))
    for _ in range(3):
        app._processar_mudanca_meet(detector.verificar([]))

    app._parar_transcricao.assert_called_once_with()
    app._status.assert_called_with("Meet encerrado. Finalizando transcricao...")


def test_modo_manual_ignora_inicio_e_fim_do_meet(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor, manual=True)

    app._processar_mudanca_meet("iniciou")
    app._processar_mudanca_meet("encerrou")

    app._iniciar_transcricao.assert_not_called()
    app._parar_transcricao.assert_not_called()
