# -*- coding: utf-8 -*-
"""Fila, escrita durável e métricas do modo de captura sem IA."""
from __future__ import annotations

import os
import queue
import time

import numpy as np
import soundcard as sc

from com_audio import com_inicializada
from config import FLUSH_AUDIO_SEG, SAMPLE_RATE


class CapturaLeveMixin:
    """Comportamentos de captura que independem de Whisper/diarização."""

    def _enfileirar_audio(self, data):
        self._registrar_frames_captura("loopback", int(getattr(data, "size", 0)))
        if self.processar_ao_vivo:
            try:
                self._q.put_nowait(data)
            except queue.Full:
                try:
                    self._q.get_nowait()
                    self._incrementar_metrica("_blocos_descartados")
                    self._q.put_nowait(data)
                except queue.Empty:
                    self._incrementar_metrica("_blocos_descartados")
            return
        # No modo posterior, jamais remover o bloco mais antigo.
        while True:
            try:
                self._q.put(data, timeout=1)
                return
            except queue.Full:
                if self._thread_proc is None or not self._thread_proc.is_alive():
                    self._incrementar_metrica("_falhas_captura")
                    self._incrementar_metrica("_blocos_descartados")
                    raise RuntimeError("processador de áudio indisponível")

    def _capturar_mic(self):
        # Mesma razão de `_capturar`: sem COM viva nesta thread o microfone
        # falha com 0x800401f0 e a gravação paralela sai vazia. Ver com_audio.
        with com_inicializada():
            self._capturar_mic_interno()

    def _capturar_mic_interno(self):
        try:
            mic = sc.default_microphone()
        except Exception as e:
            self._registrar_erro_captura_fonte("microfone")
            self.on_status(f"Erro ao abrir microfone: {e}")
            return
        frames = int(SAMPLE_RATE * 1.0)
        try:
            with mic.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
                while not self._stop.is_set():
                    try:
                        data = rec.record(numframes=frames)
                    except Exception:
                        self._registrar_erro_captura_fonte("microfone")
                        time.sleep(0.5)
                        continue
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    data = data.astype(np.float32)
                    self._registrar_frames_captura("microfone", int(data.size))
                    if self._wav_mic:
                        try:
                            with self._audio_io_lock:
                                self._wav_mic.writeframes(
                                    (data * 32767).astype(np.int16).tobytes()
                                )
                        except Exception:
                            self._incrementar_metrica("_falhas_gravacao")
                            raise
        except Exception as e:
            self.on_status(f"Erro na captura do microfone: {e}")

    def _gravar_audio_bloco(self, audio):
        if self._wav is None or audio is None or getattr(audio, "size", 0) <= 0:
            return
        try:
            with self._audio_io_lock:
                self._wav.writeframes((audio * 32767).astype(np.int16).tobytes())
            with self._metricas_lock:
                self._frames_gravados += int(audio.size)
                self._segundos_desde_flush += float(audio.size) / SAMPLE_RATE
                deve_flush = self._segundos_desde_flush >= FLUSH_AUDIO_SEG
                if deve_flush:
                    self._segundos_desde_flush = 0.0
            if deve_flush:
                self._flush_audio()
            self._checar_disco_livre()
        except Exception:
            self._incrementar_metrica("_falhas_gravacao")
            raise

    def _incrementar_metrica(self, atributo, quantidade=1):
        with self._metricas_lock:
            setattr(self, atributo, getattr(self, atributo) + quantidade)

    def _resetar_metricas_captura(self) -> None:
        """Inicializa métricas por fonte sem inspecionar o conteúdo de áudio."""
        agora = time.monotonic()
        with self._metricas_lock:
            self._frames_gravados = 0
            self._falhas_captura = 0
            self._falhas_gravacao = 0
            self._blocos_descartados = 0
            self._segundos_desde_flush = 0.0
            self._fontes_captura = {
                "loopback": {
                    "frames": 0,
                    "ultimo_frame_monotonic": agora,
                    "erros_consecutivos": 0,
                },
                "microfone": {
                    "frames": 0,
                    "ultimo_frame_monotonic": agora,
                    "erros_consecutivos": 0,
                },
            }
            self._lacunas_captura = []
            self._disco_captura = {
                "livre_bytes": None,
                "estado": "desconhecido",
            }

    def _registrar_frames_captura(self, fonte: str, frames: int) -> None:
        if frames <= 0:
            return
        lacuna_fechada = False
        with self._metricas_lock:
            dados = self._fontes_captura[fonte]
            dados["frames"] += frames
            dados["ultimo_frame_monotonic"] = time.monotonic()
            dados["erros_consecutivos"] = 0
            for lacuna in reversed(self._lacunas_captura):
                if lacuna["fonte"] == fonte and lacuna["fim_monotonic"] is None:
                    lacuna["fim_monotonic"] = dados["ultimo_frame_monotonic"]
                    lacuna_fechada = True
                    break
        if lacuna_fechada:
            self.on_status(f"Captura {fonte} retomada após lacuna.")

    def _registrar_erro_captura_fonte(self, fonte: str) -> None:
        with self._metricas_lock:
            self._falhas_captura += 1
            dados = self._fontes_captura[fonte]
            dados["erros_consecutivos"] += 1
            dados["ultimo_erro_monotonic"] = time.monotonic()

    def registrar_lacuna_captura(self, fonte: str, motivo: str) -> None:
        """Persiste um marcador sem conteúdo quando o dispositivo deixa uma lacuna."""
        with self._metricas_lock:
            if any(
                lacuna["fonte"] == fonte and lacuna["fim_monotonic"] is None
                for lacuna in self._lacunas_captura
            ):
                return
            inicio = self._fontes_captura[fonte]["ultimo_frame_monotonic"]
            self._lacunas_captura.append(
                {
                    "fonte": fonte,
                    "motivo": motivo,
                    "inicio_monotonic": inicio,
                    "fim_monotonic": None,
                }
            )
        with self._resultado_io_lock:
            if self._arq:
                horario = time.strftime("%H:%M:%S")
                self._arq.write(f"[{horario}] (Lacuna de captura: {fonte}; {motivo})\n")
                self._arq.flush()
        self.on_status(f"Lacuna de captura em {fonte}: {motivo}.")

    def _registrar_espaco_disco(self, livre_bytes: int) -> None:
        estado = "sem_espaco" if livre_bytes <= 0 else "disponivel"
        with self._metricas_lock:
            self._disco_captura = {
                "livre_bytes": int(livre_bytes),
                "estado": estado,
            }

    def _escritor_de_audio_ainda_vivo(self) -> bool:
        """Nenhum artefato é fechado enquanto uma thread de captura estiver ativa."""
        return any(
            thread is not None and thread.is_alive()
            for thread in (self._thread_cap, self._thread_proc, self._thread_mic)
        )

    def _flush_audio(self):
        """Descarrega buffers dos WAVs abertos para reduzir perda após crash."""
        with self._audio_io_lock:
            for wav in (self._wav, self._wav_mic):
                arquivo = getattr(wav, "_file", None) if wav is not None else None
                if arquivo is None:
                    continue
                arquivo.flush()
                try:
                    os.fsync(arquivo.fileno())
                except (AttributeError, OSError):
                    pass

    def metricas_captura(self) -> dict:
        with self._metricas_lock:
            return {
                "frames_gravados": self._frames_gravados,
                "falhas_captura": self._falhas_captura,
                "falhas_gravacao": self._falhas_gravacao,
                "blocos_descartados": self._blocos_descartados,
                "fila_pendente": self._q.qsize(),
                "fontes": {
                    fonte: dict(dados)
                    for fonte, dados in self._fontes_captura.items()
                },
                "lacunas": tuple(dict(lacuna) for lacuna in self._lacunas_captura),
                "disco": dict(self._disco_captura),
            }

    def _processar_somente_audio(self):
        """Grava WAV sem IA e drena até a captura efetivamente terminar."""
        try:
            while True:
                try:
                    self._gravar_audio_bloco(self._q.get(timeout=0.5))
                except queue.Empty:
                    captura_viva = bool(
                        self._thread_cap is not None and self._thread_cap.is_alive()
                    )
                    if self._stop.is_set() and not captura_viva and self._q.empty():
                        break
        finally:
            self._fechar_arquivos_no_processar()
