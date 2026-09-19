# -*- coding: utf-8 -*-
"""Watchdog — monitora threads críticas e reinicia se morrerem.

Verifica a cada INTERVALO_WATCHDOG segundos se as threads de captura
e processamento do Transcritor estão vivas. Se uma morrer, reinicia.
Após LIMITE_REINICIOS consecutivos, notifica erro crítico e para.
"""

import logging
import threading
import time

from config import (
    CAPTURA_ERROS_CONSECUTIVOS_LIMITE,
    CAPTURA_SEM_FRAMES_FALHA_SEG,
    INTERVALO_WATCHDOG,
    LIMITE_REINICIOS,
)

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
        self._reinicios = {"captura": 0, "processar": 0, "microfone": 0}
        self._fontes_com_falha: set[str] = set()

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

        self._verificar_microfone(t)

        # Verifica thread de processamento
        if t._thread_proc is None or not t._thread_proc.is_alive():
            modo_posterior = not getattr(t, "processar_ao_vivo", True)
            rotulo = "gravação em disco" if modo_posterior else "processamento"
            self._reinicios["processar"] += 1
            if self._reinicios["processar"] <= LIMITE_REINICIOS:
                logger.warning(
                    "Thread de %s morta. Reiniciando (%d/%d)...",
                    rotulo,
                    self._reinicios["processar"],
                    LIMITE_REINICIOS,
                )
                self.on_status(
                    f"Watchdog: reiniciando {rotulo} "
                    f"({self._reinicios['processar']}/{LIMITE_REINICIOS})"
                )
                t._reiniciar_processar()
            else:
                self.on_erro_critico(
                    "Gravação em disco falhou múltiplas vezes. Áudio pode estar incompleto."
                    if modo_posterior
                    else "Processamento falhou múltiplas vezes. Transcrição comprometida."
                )
                self._reinicios["processar"] = 0
        else:
            self._reinicios["processar"] = 0

        self._verificar_progresso_captura(t)
        self._verificar_disco(t)

    def _verificar_microfone(self, transcritor) -> None:
        if not getattr(transcritor, "capturar_mic", False):
            self._reinicios["microfone"] = 0
            return
        thread_mic = getattr(transcritor, "_thread_mic", None)
        if thread_mic is not None and thread_mic.is_alive():
            self._reinicios["microfone"] = 0
            return
        self._reinicios["microfone"] += 1
        if self._reinicios["microfone"] <= LIMITE_REINICIOS:
            self.on_status(
                f"Watchdog: reiniciando microfone "
                f"({self._reinicios['microfone']}/{LIMITE_REINICIOS})"
            )
            reiniciar = getattr(transcritor, "_reiniciar_microfone", None)
            if callable(reiniciar):
                reiniciar()
            return
        self.on_erro_critico(
            "Microfone indisponível — gravação da sua voz pode estar incompleta."
        )
        self._reinicios["microfone"] = 0

    def _verificar_progresso_captura(self, transcritor) -> None:
        """Distingue silêncio (frames avançam) de uma fonte de áudio parada."""
        try:
            fontes = transcritor.metricas_captura().get("fontes", {})
        except Exception:  # noqa: BLE001
            return
        agora = time.monotonic()
        for fonte, dados in fontes.items():
            if fonte == "microfone" and not getattr(transcritor, "capturar_mic", False):
                self._fontes_com_falha.discard(fonte)
                continue
            if fonte == "microfone":
                thread_mic = getattr(transcritor, "_thread_mic", None)
                if thread_mic is None or not thread_mic.is_alive():
                    continue
            ultimo_frame = dados.get("ultimo_frame_monotonic")
            if ultimo_frame is None:
                continue
            erros = int(dados.get("erros_consecutivos", 0))
            sem_frames = agora - float(ultimo_frame) >= CAPTURA_SEM_FRAMES_FALHA_SEG
            dispositivo_perdido = erros >= CAPTURA_ERROS_CONSECUTIVOS_LIMITE
            if not sem_frames and not dispositivo_perdido:
                self._fontes_com_falha.discard(fonte)
                continue
            if fonte in self._fontes_com_falha:
                continue
            self._fontes_com_falha.add(fonte)
            motivo = (
                "dispositivo indisponível"
                if dispositivo_perdido
                else "sem novos frames"
            )
            registrar_lacuna = getattr(transcritor, "registrar_lacuna_captura", None)
            if callable(registrar_lacuna):
                registrar_lacuna(fonte, motivo)
            self.on_erro_critico(
                f"Captura {fonte} falhou: {motivo}. Verifique o dispositivo de áudio."
            )

    def _verificar_disco(self, transcritor) -> None:
        try:
            estado = transcritor.metricas_captura().get("disco", {}).get("estado")
        except Exception:  # noqa: BLE001
            return
        chave = "__disco__"
        if estado != "sem_espaco":
            self._fontes_com_falha.discard(chave)
            return
        if chave in self._fontes_com_falha:
            return
        self._fontes_com_falha.add(chave)
        self.on_erro_critico(
            "Captura interrompida: sem espaço em disco para preservar o áudio."
        )
