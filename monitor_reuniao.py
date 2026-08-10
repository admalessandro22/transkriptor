# -*- coding: utf-8 -*-
"""Peças do monitor de reunião usadas pelo app de bandeja (FR-9.B/FR-9.C).

Separado de `transkriptor.pyw` para manter o bootstrap dentro do limite de 500
linhas (FR-8.2) e para deixar estas funções testáveis sem subir a bandeja.
"""

from __future__ import annotations

import logging

import pygetwindow as gw

from config import (
    DETECTAR_POR_MICROFONE,
    DETECTAR_ZOOM,
    EXIGIR_JANELA_VISIVEL,
    FATOR_TRAVAMENTO_MONITOR,
    INTERVALO_MONITOR_MEET,
)
from deteccao_reuniao import (
    DetectorReuniao,
    FonteMicrofone,
    FontePonte,
    FonteTitulo,
    FonteZoom,
)

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


def construir_detector(
    bridge, usar_microfone=DETECTAR_POR_MICROFONE, usar_zoom=DETECTAR_ZOOM
):
    """Monta o detector com as fontes disponíveis, na ordem de diagnóstico."""
    fontes = [FonteTitulo(listar_janelas, EXIGIR_JANELA_VISIVEL)]
    if usar_zoom:
        # O título do Zoom muda com o idioma; esta fonte olha a classe da
        # janela e o microfone do zoom.exe (FR-10.A3).
        fontes.append(FonteZoom())
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


MSG_MONITOR_TRAVADO = (
    "O monitor de reuniões parou de responder — nenhuma reunião será detectada. "
    "Reinicie o Transkriptor e veja o log."
)


class VigiaMonitor:
    """Alarma quando o loop do monitor para de bater (FR-9.C4).

    O heartbeat no log só ajuda quem está lendo o log. Em 2026-08-07 o monitor
    travou e o app passou três dias na bandeja com o ícone normal. O vigia roda
    numa thread separada justamente para sobreviver ao travamento do monitor.
    """

    def __init__(
        self,
        on_travado,
        intervalo=INTERVALO_MONITOR_MEET,
        fator=FATOR_TRAVAMENTO_MONITOR,
    ):
        self._on_travado = on_travado
        self.limite = intervalo * fator
        self._ultimo_tick = None
        self._alarmado = False

    def bater(self, agora):
        """Chamado a cada ciclo do monitor: prova de vida."""
        self._ultimo_tick = agora
        self._alarmado = False

    def verificar(self, agora):
        """True no ciclo em que o travamento é detectado. Não repete o alarme."""
        if self._ultimo_tick is None or self._alarmado:
            return False
        if agora - self._ultimo_tick <= self.limite:
            return False
        self._alarmado = True
        logger.error(
            "Monitor sem sinal de vida há %.0fs (limite %.0fs).",
            agora - self._ultimo_tick,
            self.limite,
        )
        try:
            self._on_travado(MSG_MONITOR_TRAVADO)
        except Exception:  # noqa: BLE001 — o alarme falhar não pode calar o vigia
            logger.exception("Falha ao avisar que o monitor travou")
        return True


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
