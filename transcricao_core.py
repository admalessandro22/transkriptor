# -*- coding: utf-8 -*-
"""Núcleo de transcrição: captura loopback + faster-whisper + diarização.

Salva o áudio em disco (WAV temporário) e os segmentos com timestamps
durante a reunião, e ao final roda a diarização (separação de falantes)
em uma thread dedicada para não bloquear o monitor de Meet.
"""

import datetime
import io
import logging
import os
import queue
import shutil
import threading
import time
import wave

import numpy as np
import soundcard as sc

from config import (
    SAMPLE_RATE,
    CHUNK_SEGUNDOS,
    MODELO_WHISPER,
    IDIOMA,
    COMPUTE_TYPE,
    DEVICE_WHISPER,
    resolver_device_whisper,
    resolver_modelo_whisper,
    detectar_cuda_e_vram,
    CAPTURAR_MIC,
    ROTULO_USUARIO,
    TIMEOUT_JOIN_STOP_SEG,
    MIN_DISCO_LIVRE_GB,
    PASTA_AUDIO,  # reexport para monkeypatch em testes
)

logger = logging.getLogger(__name__)


def WhisperModel(*args, **kwargs):
    """Factory lazy compatível com os testes sem importar IA na captura."""
    from faster_whisper import WhisperModel as ModeloWhisper

    return ModeloWhisper(*args, **kwargs)


class Transcritor:
    """Captura o áudio do alto-falante, transcreve com Whisper e diariza ao final."""

    def __init__(
        self,
        modelo=MODELO_WHISPER,
        idioma=IDIOMA,
        pasta_saida="transcricoes",
        dispositivo="",
        chunk=CHUNK_SEGUNDOS,
        diarizar_ao_final=True,
        num_falantes=None,
        on_status=None,
        capturar_mic=CAPTURAR_MIC,
        identificar_voz=True,
        rotulo_usuario=ROTULO_USUARIO,
        eventos_meet=None,
        usar_vozes_conhecidas=True,
        criptografar=None,
        processar_ao_vivo=True,
    ):
        self.modelo_nome = modelo
        self.idioma = None if idioma == "auto" else idioma
        self.pasta_saida = pasta_saida
        self.dispositivo = dispositivo
        self.chunk = chunk
        self.diarizar_ao_final = diarizar_ao_final
        self.num_falantes = num_falantes
        self.on_status = on_status or (lambda _msg: None)
        self.capturar_mic = capturar_mic
        self.identificar_voz = identificar_voz
        self.rotulo_usuario = rotulo_usuario
        self.eventos_meet = list(eventos_meet or [])
        self.usar_vozes_conhecidas = usar_vozes_conhecidas
        self.processar_ao_vivo = bool(processar_ao_vivo)
        if criptografar is None:
            from crypto_storage import chave_disponivel, criptografia_ativa

            criptografar = criptografia_ativa() and chave_disponivel()
        self.criptografar = criptografar
        self._centroides_por_rotulo_ultima: dict = {}

        self._modelo = None
        self._stop = threading.Event()
        self._q = queue.Queue(maxsize=120)
        self._thread_cap = None
        self._thread_proc = None
        self._thread_mic = None
        self._arq = None
        self._wav = None
        self._wav_mic = None
        self._caminho_saida = None
        self._caminho_wav = None
        self._caminho_wav_mic = None
        self.rodando = False
        self.diarizando = False
        self.finalizando = False
        self._somente_audio = not self.processar_ao_vivo
        self.audios_preservados: list[str] = []
        self._thread_diar = None

        # dados para diarização (leves: só timestamps + texto, sem áudio)
        self._segmentos = []  # [(start_sec, end_sec, texto)]
        self._offset_seg = 0.0

        os.makedirs(self.pasta_saida, exist_ok=True)

    def _carregar_modelo(self):
        if self._modelo is not None:
            return
        nome = self.modelo_nome or MODELO_WHISPER
        if nome == "auto":
            tem_cuda, vram_gb = detectar_cuda_e_vram()
            modelo, device, ctype = resolver_modelo_whisper(tem_cuda, vram_gb)
            self.on_status(f"Carregando modelo {modelo} ({device}, auto)...")
            try:
                self._modelo = WhisperModel(modelo, device=device, compute_type=ctype)
            except Exception as e:
                logger.warning("Falha Whisper %s/%s: %s; small/cpu", modelo, device, e)
                self.on_status("Falha no modelo GPU — carregando small em CPU...")
                self._modelo = WhisperModel("small", device="cpu", compute_type="int8")
            self.on_status("Modelo pronto.")
            return
        self.on_status(f"Carregando modelo {nome}...")
        device = resolver_device_whisper(DEVICE_WHISPER)
        self._modelo = WhisperModel(nome, device=device, compute_type=COMPUTE_TYPE)
        self.on_status("Modelo pronto.")

    def _abrir_wav(self, caminho):
        w = wave.open(caminho, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        return w

    def _abrir_arquivo(self):
        from crypto_storage import caminho_transcricao_novo

        self._caminho_saida = caminho_transcricao_novo(
            self.pasta_saida, criptografar=self.criptografar
        )
        cab = f"=== Transcricao iniciada em {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n\n"
        if self.criptografar:
            self._arq = io.StringIO()
            self._arq.write(cab)
        else:
            self._arq = open(self._caminho_saida, "w", encoding="utf-8")
            self._arq.write(cab)
            self._arq.flush()
        base = os.path.splitext(self._caminho_saida)[0]
        self._caminho_wav = base + "_audio.wav"
        self._wav = self._abrir_wav(self._caminho_wav)
        if self.capturar_mic:
            self._caminho_wav_mic = base + "_mic.wav"
            self._wav_mic = self._abrir_wav(self._caminho_wav_mic)

    def _abrir_loopback(self):
        if self.dispositivo:
            speaker = next(
                (
                    s for s in sc.all_speakers()
                    if getattr(s, "name", "") == self.dispositivo
                    or getattr(s, "id", "") == self.dispositivo
                ),
                sc.default_speaker(),
            )
        else:
            speaker = sc.default_speaker()
        loop_id = getattr(speaker, "id", None) or str(getattr(speaker, "name", ""))
        return sc.get_microphone(id=loop_id, include_loopback=True)

    def _capturar(self):
        try:
            mic = self._abrir_loopback()
        except Exception as e:
            self.on_status(f"Erro ao abrir audio: {e}")
            self._stop.set()
            return
        frames = int(SAMPLE_RATE * 1.0)
        self.on_status(f"Capturando audio... ({SAMPLE_RATE} Hz)")
        try:
            with mic.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
                while not self._stop.is_set():
                    try:
                        data = rec.record(numframes=frames)
                    except Exception:
                        time.sleep(0.5)
                        continue
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    data = data.astype(np.float32)
                    self._enfileirar_audio(data)
        except Exception as e:
            self.on_status(f"Erro na captura: {e}")

    def _enfileirar_audio(self, data):
        if self.processar_ao_vivo:
            try:
                self._q.put_nowait(data)
            except queue.Full:
                try:
                    self._q.get_nowait()
                    self._q.put_nowait(data)
                except queue.Empty:
                    pass
            return
        # Captura posterior: nunca remove o bloco mais antigo. O consumidor de
        # disco é leve e deve liberar espaço; o timeout só permite reavaliar a
        # saúde da thread sem transformar a captura em espera infinita opaca.
        while True:
            try:
                self._q.put(data, timeout=1)
                return
            except queue.Full:
                if self._thread_proc is None or not self._thread_proc.is_alive():
                    raise RuntimeError("processador de áudio indisponível")

    def _capturar_mic(self):
        try:
            mic = sc.default_microphone()
        except Exception as e:
            self.on_status(f"Erro ao abrir microfone: {e}")
            return
        frames = int(SAMPLE_RATE * 1.0)
        try:
            with mic.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
                while not self._stop.is_set():
                    try:
                        data = rec.record(numframes=frames)
                    except Exception:
                        time.sleep(0.5)
                        continue
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    data = data.astype(np.float32)
                    if self._wav_mic:
                        self._wav_mic.writeframes((data * 32767).astype(np.int16).tobytes())
        except Exception as e:
            self.on_status(f"Erro na captura do microfone: {e}")

    def _gravar_audio_bloco(self, audio):
        if self._wav is not None and audio is not None and getattr(audio, "size", 0) > 0:
            self._wav.writeframes((audio * 32767).astype(np.int16).tobytes())

    def _fechar_arquivos_no_processar(self):
        """FR-6.1: fecha só se stop(); restart do watchdog mantém arquivos abertos."""
        if not self._stop.is_set():
            return
        try:
            self._finalizar_arquivo_texto()
        except Exception:
            pass
        try:
            if self._wav:
                self._wav.close()
                self._wav = None
        except Exception:
            pass

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

    def _processar(self):
        try:
            alvo = int(SAMPLE_RATE * self.chunk)
            buffer, buf_n = [], 0
            while not self._stop.is_set():
                try:
                    pedaco = self._q.get(timeout=0.5)
                except queue.Empty:
                    continue
                buffer.append(pedaco)
                buf_n += pedaco.size
                if buf_n >= alvo:
                    self._transcrever_bloco(np.concatenate(buffer))
                    buffer, buf_n = [], 0
            if buffer:
                self._transcrever_bloco(np.concatenate(buffer), final=True)
        finally:
            self._fechar_arquivos_no_processar()

    def _fechar_wav_mic(self):
        try:
            if self._wav_mic:
                self._wav_mic.close()
                self._wav_mic = None
        except Exception:
            pass

    def _transcrever_bloco(self, audio, final=False):
        if audio.size == 0:
            return
        duracao = audio.size / SAMPLE_RATE
        self._gravar_audio_bloco(audio)  # FR-2.4: WAV sempre, independente do Whisper
        if self._modelo is None:
            self._offset_seg += duracao
            return
        try:
            segments, _info = self._modelo.transcribe(
                audio, language=self.idioma, vad_filter=True, beam_size=1,
                vad_parameters={"min_silence_duration_ms": 600},
            )
            segmentos_lista = list(segments)
        except Exception as e:
            self.on_status(f"Erro na transcrição: {e}")
            self._offset_seg += duracao
            return
        texto_completo = []
        for seg in segmentos_lista:
            texto = seg.text.strip()
            if not texto:
                continue
            if self.diarizar_ao_final:
                self._segmentos.append(
                    (self._offset_seg + seg.start, self._offset_seg + seg.end, texto)
                )
            texto_completo.append(texto)
        self._offset_seg += duracao
        texto = " ".join(texto_completo).strip()
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        if self._arq:
            self._arq.write(f"[{ts}] {texto if texto else '(silencio)'}\n")
            self._arq.flush()
        if texto:
            self.on_status(texto)

    def _rodar_diarizacao(self, caminho_saida, caminho_wav):
        from diarizacao_final import rodar_diarizacao
        rodar_diarizacao(self, caminho_saida, caminho_wav)

    def _preservar_audios(self, *caminhos):
        from diarizacao_final import preservar_audios
        return preservar_audios(self.criptografar, *caminhos, pasta_audio=PASTA_AUDIO)

    def _checar_disco_livre(self):
        try:
            livre = shutil.disk_usage(self.pasta_saida).free
            if livre < MIN_DISCO_LIVRE_GB * (1024**3):
                self.on_status(
                    f"Aviso: pouco espaço em disco "
                    f"(menos de {MIN_DISCO_LIVRE_GB} GB livres). A gravação continua."
                )
        except Exception:
            logger.debug("Não foi possível checar espaço em disco", exc_info=True)

    def start(self):
        if self.rodando:
            return
        self._checar_disco_livre()
        self._abrir_arquivo()
        self._stop.clear()
        self._segmentos = []
        self._offset_seg = 0.0
        self.diarizando = False
        self._somente_audio = not self.processar_ao_vivo
        self.audios_preservados = []
        self.rodando = True
        if not self.processar_ao_vivo:
            self._thread_proc = threading.Thread(
                target=self._processar_somente_audio,
                daemon=True,
                name="Transkriptor-GravacaoWav",
            )
            self._thread_proc.start()
        self._thread_cap = threading.Thread(target=self._capturar, daemon=True)
        self._thread_cap.start()
        if self.capturar_mic:
            self._thread_mic = threading.Thread(target=self._capturar_mic, daemon=True)
            self._thread_mic.start()
        if not self.processar_ao_vivo:
            self.on_status("Gravação da reunião em andamento.")
            return
        try:
            self._carregar_modelo()
        except Exception as e:
            self._somente_audio = True
            self._modelo = None
            self.on_status(
                "Transcrição indisponível — gravando somente áudio para retranscrição"
            )
            logger.warning("Whisper indisponível; modo somente áudio: %s", e)
            self._thread_proc = threading.Thread(
                target=self._processar_somente_audio, daemon=True
            )
            self._thread_proc.start()
            return
        self._thread_proc = threading.Thread(target=self._processar, daemon=True)
        self._thread_proc.start()

    def _aguardar_thread(self, thread, timeout=TIMEOUT_JOIN_STOP_SEG):
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def _finalizar_arquivo_texto(self):
        if not self._arq:
            return
        self._arq.write(
            f"\n=== Encerrado em {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n"
        )
        if self.criptografar and isinstance(self._arq, io.StringIO):
            from crypto_storage import salvar_transcricao
            salvar_transcricao(self._caminho_saida, self._arq.getvalue())
            self._arq = None
            return
        self._arq.close()
        self._arq = None

    def _fechar_arquivos_abertos(self):
        try:
            self._finalizar_arquivo_texto()
        except Exception:
            pass
        try:
            if self._wav:
                self._wav.close()
                self._wav = None
        except Exception:
            pass

    def descartar(self):
        """FR-2.9: para e apaga os arquivos desta gravação (recusa do usuário)."""
        self._descartar = True
        self.diarizar_ao_final = False
        return self.stop()

    def _apagar_descartados(self, *caminhos):
        for c in caminhos:
            if c and os.path.isfile(c):
                try:
                    os.remove(c)
                except OSError:
                    logger.warning("Falha ao apagar arquivo descartado %s", c)

    def stop(self):
        if not self.rodando:
            return None
        self.finalizando = True
        self._stop.set()
        self._aguardar_thread(self._thread_cap)
        self._aguardar_thread(self._thread_proc)
        if self._thread_mic and self._thread_mic.is_alive():
            self._aguardar_thread(self._thread_mic)
        self._fechar_wav_mic()
        if self._thread_proc and self._thread_proc.is_alive():
            self._aguardar_thread(self._thread_proc, timeout=5)
        self._fechar_arquivos_abertos()
        self.rodando = False
        caminho, caminho_wav = self._caminho_saida, self._caminho_wav
        self._caminho_wav_mic_salvo = self._caminho_wav_mic
        descartado = getattr(self, "_descartar", False)
        if descartado:
            self._apagar_descartados(caminho, caminho_wav, self._caminho_wav_mic_salvo)
            caminho = None
        elif self.diarizar_ao_final and self._segmentos and caminho:
            self._thread_diar = threading.Thread(
                target=self._rodar_diarizacao, args=(caminho, caminho_wav), daemon=True
            )
            self._thread_diar.start()
        else:
            self.audios_preservados = self._preservar_audios(
                caminho_wav, self._caminho_wav_mic_salvo
            )
        self._caminho_saida = None
        self.finalizando = False
        self.on_status("Gravação descartada." if descartado else "Transcrição encerrada.")
        return caminho

    def _reiniciar_captura(self):
        if self.rodando and (self._thread_cap is None or not self._thread_cap.is_alive()):
            self.on_status("Reiniciando captura (watchdog)...")
            self._thread_cap = threading.Thread(target=self._capturar, daemon=True)
            self._thread_cap.start()

    def _reiniciar_processar(self):
        """FR-2.4×FR-6.1: em só-áudio reinicia `_processar_somente_audio`."""
        if self.rodando and (self._thread_proc is None or not self._thread_proc.is_alive()):
            self.on_status("Reiniciando processamento (watchdog)...")
            alvo = (
                self._processar_somente_audio
                if getattr(self, "_somente_audio", False)
                else self._processar
            )
            self._thread_proc = threading.Thread(target=alvo, daemon=True)
            self._thread_proc.start()

    def caminho_atual(self):
        return self._caminho_saida
