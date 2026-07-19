# -*- coding: utf-8 -*-
"""Watchdog — monitora threads críticas e reinicia se morrerem.

Verifica a cada INTERVALO_WATCHDOG segundos se as threads de captura
e processamento do Transcritor estão vivas. Se uma morrer, reinicia.
Após LIMITE_REINICIOS consecutivos, notifica erro crítico e para.
"""

import logging
import threading

from config import INTERVALO_WATCHDOG, LIMITE_REINICIOS

logger = logging.getLogger(__name__)


class Watchdog:
    """Monitora threads críticas do Transcritor."""

    def __init__(self, transcritor, on_status=None, on_erro_critico=None,
                 intervalo=INTERVALO_WATCHDOG):
        self.transcritor = transcritor
        self.on_status = on_status or (lambda _msg: None)
        self.on_erro_critico = on_erro_critico or (lambda _msg: None)
        self.intervalo = intervalo
        self._stop = threading.Event()
        self._thread = None
        self._reinicios = {"captura": 0, "processar": 0}

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Watchdog iniciado.")

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _loop(self):
        while not self._stop.is_set():
            self._verificar()
            self._stop.wait(self.intervalo)

    def _verificar(self):
        t = self.transcritor
        if t is None or not t.rodando or getattr(t, "finalizando", False):
            return

        # Verifica thread de captura
        if t._thread_cap is None or not t._thread_cap.is_alive():
            self._reinicios["captura"] += 1
            if self._reinicios["captura"] <= LIMITE_REINICIOS:
                logger.warning("Thread de captura morta. Reiniciando (%d/%d)...",
                               self._reinicios["captura"], LIMITE_REINICIOS)
                self.on_status(f"Watchdog: reiniciando captura ({self._reinicios['captura']}/{LIMITE_REINICIOS})")
                t._reiniciar_captura()
            else:
                # FR-6.2: toast específico após 3 falhas consecutivas de captura
                self.on_erro_critico(
                    "Sem áudio do sistema — verifique o dispositivo de saída"
                )
                self._reinicios["captura"] = 0
        else:
            self._reinicios["captura"] = 0

        # Verifica thread de processamento
        if t._thread_proc is None or not t._thread_proc.is_alive():
            self._reinicios["processar"] += 1
            if self._reinicios["processar"] <= LIMITE_REINICIOS:
                logger.warning("Thread de processamento morta. Reiniciando (%d/%d)...",
                               self._reinicios["processar"], LIMITE_REINICIOS)
                self.on_status(f"Watchdog: reiniciando processamento ({self._reinicios['processar']}/{LIMITE_REINICIOS})")
                t._reiniciar_processar()
            else:
                self.on_erro_critico("Processamento falhou múltiplas vezes. Transcrição comprometida.")
                self._reinicios["processar"] = 0
        else:
            self._reinicios["processar"] = 0
