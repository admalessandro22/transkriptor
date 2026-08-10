# -*- coding: utf-8 -*-
"""Ciclo de uma reunião: consentimento → captura → encerramento (FR-10.B/FR-10.D).

Separado de `transkriptor.pyw` para manter o bootstrap dentro do limite de 500
linhas (FR-8.2) e para deixar o ciclo testável sem subir a bandeja.

**Regra que não pode regredir:** nada que dispare callback de status roda sob
`self._lock`. Em 2026-08-07 `Transcritor.start()` foi chamado segurando o lock,
e `start()` chama `on_status` — que é `_status`, que pedia o mesmo lock. O app
ficou três dias vivo na bandeja sem gravar um frame e sem uma linha no log.
Ver `tests/test_ciclo_reuniao_sem_deadlock.py` e `tests/test_lock_sem_callback.py`.
"""

from __future__ import annotations

import logging
import threading
import time

from config import (
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_PERFIL_VOZ_ENC,
    IDIOMA,
    LIMITE_PORTAO_CONSENTIMENTO_SEG,
    MODELO_WHISPER,
    PASTA_TRANSCRICOES,
)
from consentimento_gravacao import pedir_consentimento
from crypto_storage import perfil_existe
from estado_icone import DURACAO_ERRO_ICONE
from notificador import notificar
from transkriptor_acoes import (
    deve_iniciar_gravacao_auto,
    deve_parar_transcricao_por_meet,
    portao_consentimento_liberado,
)
from watchdog import Watchdog

logger = logging.getLogger(__name__)


class CicloReuniaoMixin:
    """Início, parada e consentimento de uma reunião detectada."""

    def _eventos_meet_relativos(self):
        if self._inicio_transcricao_wall_ms is None:
            return []
        inicio = self._inicio_transcricao_wall_ms
        relativos = []
        for ev in self.meet_bridge.drenar_eventos():
            ts_ms = ev.get("ts_ms", int(ev.get("ts_sec", 0) * 1000))
            relativos.append({**ev, "ts_sec": (ts_ms - inicio) / 1000.0})
        return relativos

    def _iniciar_transcricao(self):
        with self._lock:
            # Pausar enquanto a caixa de consentimento estava aberta não pode
            # abrir captura depois que o usuário clicar em Sim.
            if not getattr(self, "deteccao_ativa", True):
                return
            # Um único portão impede duas capturas simultâneas no loopback.
            if getattr(self, "_iniciando", False) or (
                self.transcritor and self.transcritor.rodando
            ):
                return
            self._iniciando = True
        try:
            self._iniciar_transcricao_interno()
        finally:
            with self._lock:
                self._iniciando = False

    def _construir_transcritor(self):
        from transcricao_core import Transcritor

        return Transcritor(
            modelo=getattr(self, "modelo_whisper", MODELO_WHISPER),
            idioma=IDIOMA,
            pasta_saida=PASTA_TRANSCRICOES,
            diarizar_ao_final=self.diarizacao_ativa,
            on_status=self._status,
            capturar_mic=self.capturar_mic,
            identificar_voz=self.identificar_minha_voz
            and perfil_existe(ARQUIVO_PERFIL_VOZ, ARQUIVO_PERFIL_VOZ_ENC),
            rotulo_usuario=self.rotulo_usuario,
            criptografar=self.criptografar_transcricoes,
            processar_ao_vivo=False,
        )

    def _iniciar_transcricao_interno(self):
        self._inicio_transcricao_wall_ms = int(time.time() * 1000)
        detector = getattr(self, "detector", None)
        fontes = ", ".join(getattr(detector, "fontes_da_reuniao", None) or []) or "?"
        self._status(f"Reunião detectada ({fontes}). Iniciando gravação...")
        self.transcritor = self._construir_transcritor()
        try:
            with self._lock:
                if not getattr(self, "deteccao_ativa", True):
                    self.transcritor = None
                    return
            # `start()` chama `on_status`, que é `_status`. Nada que dispare
            # callback pode rodar sob `self._lock`. A corrida com Pausar é
            # fechada depois, desfazendo, e não segurando o lock durante o start.
            self.transcritor.start()
            if self._pausou_durante_o_start():
                self._status("Detecção pausada; encerrando a gravação recém-iniciada.")
                self._parar_transcricao()
                return
            self.watchdog = Watchdog(
                self.transcritor,
                on_status=self._status,
                on_erro_critico=self._erro_critico,
            )
            self.watchdog.start()
            self._status("Transcricao em andamento.")
            notificar("Transkriptor", "Transcrição iniciada (reunião detectada)")
            self._atualizar_tooltip()
        except Exception as e:
            self._status(f"Erro ao iniciar: {e}")
            notificar("Transkriptor", f"Erro ao iniciar transcrição: {e}")

    def _pausou_durante_o_start(self):
        """True se Pausar entrou entre a validação e a abertura do áudio."""
        with self._lock:
            return not getattr(self, "deteccao_ativa", True)

    def _erro_critico(self, msg):
        self._em_erro = True
        self._instante_erro = time.monotonic()
        logging.error("Erro critico: %s", msg)
        self._status(f"ERRO CRITICO: {msg}")
        notificar("Transkriptor", f"Erro crítico: {msg}. Veja o log.")
        self._atualizar_tooltip()

        def _reverter_erro():
            time.sleep(DURACAO_ERRO_ICONE)
            self._em_erro = False
            self._instante_erro = None
            self._atualizar_tooltip()

        threading.Thread(target=_reverter_erro, daemon=True).start()

    def _parar_transcricao(self):
        with self._lock:
            t, w = self.transcritor, self.watchdog
        if w:
            w.stop()
            self.watchdog = None
        if t and t.rodando:
            if self.usar_nomes_meet:
                t.eventos_meet = self._eventos_meet_relativos()
                if self.modo_legendas_meet and not t.eventos_meet:
                    notificar(
                        "Transkriptor",
                        "Ative legendas no Meet para identificar participantes",
                    )
            caminho = t.stop()
            with self._lock:
                if self.transcritor is t:
                    self.transcritor = None
            if caminho:
                self._enfileirar_reuniao(t, caminho)
            self._atualizar_tooltip()

    def _em_thread(self, alvo, nome):
        """Executa fora da thread do monitor.

        Carregar o Whisper e finalizar a diarização levam dezenas de segundos.
        Rodando no monitor, a detecção ficava cega justamente durante o início e
        o fim da reunião.
        """
        threading.Thread(target=alvo, daemon=True, name=nome).start()

    def _processar_mudanca_meet(self, mudanca):
        if mudanca == "iniciou":
            if deve_iniciar_gravacao_auto(self._recusa_reuniao_ativa):
                with self._lock:
                    if not portao_consentimento_liberado(
                        self._consentimento_em_andamento,
                        getattr(self, "_consentimento_aberto_em", None),
                        time.monotonic(),
                        LIMITE_PORTAO_CONSENTIMENTO_SEG,
                    ):
                        return
                    self._consentimento_em_andamento = True
                    self._consentimento_aberto_em = time.monotonic()
                self._em_thread(self._pedir_e_iniciar, "Transkriptor-Consentimento")
            return
        if mudanca == "encerrou":
            # FR-2.10: recusa vale só para a reunião que acabou
            self._recusa_reuniao_ativa = False
        if deve_parar_transcricao_por_meet(mudanca):
            self._status("Reunião encerrada. Finalizando transcricao...")
            self._em_thread(self._parar_transcricao, "Transkriptor-Fim")

    def _pedir_e_iniciar(self):
        """Solicita consentimento antes de abrir dispositivo ou arquivo de áudio."""
        try:
            perguntar = getattr(self, "_pedir_consentimento", None) or pedir_consentimento
            autorizado = bool(perguntar())
            detector = getattr(self, "detector", None)
            reuniao_ainda_ativa = bool(
                detector is not None and getattr(detector, "reuniao_ativa", False)
            )
            if not autorizado:
                if reuniao_ainda_ativa:
                    self._recusa_reuniao_ativa = True
                    self._status("Esta reunião não será gravada.")
                return
            if not reuniao_ainda_ativa:
                return
            if not getattr(self, "deteccao_ativa", True):
                self._status("Detecção pausada; reunião não será gravada.")
                return
            self._iniciar_transcricao()
        finally:
            with self._lock:
                self._consentimento_em_andamento = False
                self._consentimento_aberto_em = None
