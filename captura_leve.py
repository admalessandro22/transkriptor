# -*- coding: utf-8 -*-
"""Fila, escrita durável e métricas do modo de captura sem IA."""
from __future__ import annotations

import os
import queue
import time

import numpy as np
import soundcard as sc

from config import FLUSH_AUDIO_SEG, SAMPLE_RATE


class CapturaLeveMixin:
    """Comportamentos de captura que independem de Whisper/diarização."""

    def _enfileirar_audio(self, data):
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
        try:
            mic = sc.default_microphone()
        except Exception as e:
            self._incrementar_metrica("_falhas_captura")
            self.on_status(f"Erro ao abrir microfone: {e}")
            return
        frames = int(SAMPLE_RATE * 1.0)
        try:
            with mic.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
                while not self._stop.is_set():
                    try:
                        data = rec.record(numframes=frames)
                    except Exception:
                        self._incrementar_metrica("_falhas_captura")
                        time.sleep(0.5)
                        continue
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    data = data.astype(np.float32)
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
        except Exception:
            self._incrementar_metrica("_falhas_gravacao")
            raise

    def _incrementar_metrica(self, atributo, quantidade=1):
        with self._metricas_lock:
            setattr(self, atributo, getattr(self, atributo) + quantidade)

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
