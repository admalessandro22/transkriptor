# -*- coding: utf-8 -*-
"""Peças do monitor de reunião usadas pelo app de bandeja (FR-9.B/FR-9.C).

Separado de `transkriptor.pyw` para manter o bootstrap dentro do limite de 500
linhas (FR-8.2) e para deixar estas funções testáveis sem subir a bandeja.
"""

from __future__ import annotations

import logging

import pygetwindow as gw

from config import DETECTAR_POR_MICROFONE, EXIGIR_JANELA_VISIVEL
from deteccao_reuniao import DetectorReuniao, FonteMicrofone, FontePonte, FonteTitulo

logger = logging.getLogger(__name__)


def listar_janelas(exigir_visivel=EXIGIR_JANELA_VISIVEL):
    """Títulos das janelas de topo, com estado de minimizada quando exigido.

    Atenção ao mexer aqui: o título de um navegador é o da **aba em primeiro
    plano**. A extensão é a fonte forte que cobre uma aba de Meet em segundo
    plano; microfone é apenas diagnóstico na v1.5.
    """
    if not exigir_visivel:
        return list(gw.getAllTitles())
    janelas = []
    for w in gw.getAllWindows():
        try:
            janelas.append({"titulo": w.title, "visivel": not w.isMinimized})
        except Exception:
            continue
    return janelas


def construir_detector(bridge, usar_microfone=DETECTAR_POR_MICROFONE):
    """Monta o detector com as fontes disponíveis, na ordem de diagnóstico."""
    fontes = [FonteTitulo(listar_janelas, EXIGIR_JANELA_VISIVEL)]
    if usar_microfone:
        fontes.append(FonteMicrofone())
    fontes.append(FontePonte(bridge))
    return DetectorReuniao(fontes)


def texto_heartbeat(detector, gravando, ciclos):
    """FR-9.C4: linha de prova de vida do monitor."""
    sinais = [s for s in getattr(detector, "ultimos_sinais", []) if s.ativo]
    fortes = ", ".join(s.fonte for s in sinais if s.forte)
    auxiliares = ", ".join(s.fonte for s in sinais if not s.forte)
    return (
        f"Monitor vivo: ciclo {ciclos}, reunião={getattr(detector, 'reuniao_ativa', False)}, "
        f"fortes=[{fortes}], auxiliares=[{auxiliares}], gravando={bool(gravando)}"
    )


def autoteste_audio(on_erro):
    """FR-9.A4: falha de captura vira aviso visível, nunca silêncio no log.

    Foi a ausência disto que deixou a captura quebrada passar despercebida.
    """
    try:
        from audio_utils import testar_loopback

        resultado = testar_loopback()
    except Exception:
        logger.exception("Autoteste de áudio falhou")
        return False
    if resultado.get("ok"):
        logger.info("Autoteste de áudio OK (%s).", resultado.get("dispositivo", ""))
        return True
    logger.error("Autoteste de áudio FALHOU: %s", resultado.get("motivo"))
    on_erro(
        "Não consigo capturar o áudio do sistema — as reuniões seriam gravadas "
        "em branco. Abra Diagnóstico no menu da bandeja."
    )
    return False
