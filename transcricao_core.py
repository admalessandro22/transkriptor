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
from faster_whisper import WhisperModel

from audio_utils import ler_trecho_wav
from config import (
    SAMPLE_RATE,
    CHUNK_SEGUNDOS,
    MODELO_WHISPER,
    IDIOMA,
    COMPUTE_TYPE,
    DEVICE_WHISPER,
    resolver_device_whisper,
    CAPTURAR_MIC,
    ARQUIVO_PERFIL_VOZ,
    ARQUIVO_VOZES_CONHECIDAS,
    LIMIAR_IDENTIFICACAO_VOZ,
    ROTULO_USUARIO,
    LIMIAR_RMS_MIC,
    TIMEOUT_JOIN_STOP_SEG,
    PASTA_AUDIO,
    MIN_DISCO_LIVRE_GB,
)

logger = logging.getLogger(__name__)


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

        # dados para diarização (leves: só timestamps + texto, sem áudio)
        self._segmentos = []  # [(start_sec, end_sec, texto)]
        self._offset_seg = 0.0

        os.makedirs(self.pasta_saida, exist_ok=True)

    def _carregar_modelo(self):
        if self._modelo is None:
            self.on_status(f"Carregando modelo {self.modelo_nome}...")
            device = resolver_device_whisper(DEVICE_WHISPER)
            self._modelo = WhisperModel(self.modelo_nome, device=device, compute_type=COMPUTE_TYPE)
            self.on_status("Modelo pronto.")

    def _abrir_arquivo(self):
        from crypto_storage import caminho_transcricao_novo

        self._caminho_saida = caminho_transcricao_novo(
            self.pasta_saida, criptografar=self.criptografar
        )
        cabecalho = (
            f"=== Transcricao iniciada em {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n\n"
        )
        if self.criptografar:
            self._arq = io.StringIO()
            self._arq.write(cabecalho)
        else:
            self._arq = open(self._caminho_saida, "w", encoding="utf-8")
            self._arq.write(cabecalho)
            self._arq.flush()

        # WAV sempre gravado (FR-2.1); ao final é movido para PASTA_AUDIO
        base = os.path.splitext(self._caminho_saida)[0]
        self._caminho_wav = base + "_audio.wav"
        self._wav = wave.open(self._caminho_wav, "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)  # int16
        self._wav.setframerate(SAMPLE_RATE)

        if self.capturar_mic:
            base = os.path.splitext(self._caminho_saida)[0]
            self._caminho_wav_mic = base + "_mic.wav"
            self._wav_mic = wave.open(self._caminho_wav_mic, "wb")
            self._wav_mic.setnchannels(1)
            self._wav_mic.setsampwidth(2)
            self._wav_mic.setframerate(SAMPLE_RATE)

    def _abrir_loopback(self):
        if self.dispositivo:
            speaker = next(
                (
                    s
                    for s in sc.all_speakers()
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
                    try:
                        self._q.put_nowait(data)
                    except queue.Full:
                        try:
                            self._q.get_nowait()
                            self._q.put_nowait(data)
                        except queue.Empty:
                            pass
        except Exception as e:
            self.on_status(f"Erro na captura: {e}")

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
        """Escreve frames no WAV (modo somente áudio ou com Whisper)."""
        if self._wav is not None and audio is not None and getattr(audio, "size", 0) > 0:
            self._wav.writeframes((audio * 32767).astype(np.int16).tobytes())

    def _fechar_arquivos_no_processar(self):
        """FR-6.1: só fecha no finally de _processar se stop() foi pedido.

        Reinício pelo watchdog (thread morreu sem stop) deve manter _arq/_wav
        abertos para a nova thread continuar gravando no mesmo arquivo.
        """
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
        """FR-2.4: grava WAV sem Whisper quando o modelo falha."""
        try:
            while not self._stop.is_set():
                try:
                    pedaco = self._q.get(timeout=0.5)
                except queue.Empty:
                    continue
                self._gravar_audio_bloco(pedaco)
            # drena fila restante
            while True:
                try:
                    pedaco = self._q.get_nowait()
                except queue.Empty:
                    break
                self._gravar_audio_bloco(pedaco)
        finally:
            self._fechar_arquivos_no_processar()

    def _processar(self):
        # FR-6.1 / BUG-08: try/finally; fecha só se stop() (não no restart do watchdog)
        try:
            alvo = int(SAMPLE_RATE * self.chunk)
            buffer = []
            buf_n = 0
            while not self._stop.is_set():
                try:
                    pedaco = self._q.get(timeout=0.5)
                except queue.Empty:
                    continue
                buffer.append(pedaco)
                buf_n += pedaco.size
                if buf_n >= alvo:
                    audio = np.concatenate(buffer)
                    buffer.clear()
                    buf_n = 0
                    self._transcrever_bloco(audio)
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
        try:
            segments, _info = self._modelo.transcribe(
                audio,
                language=self.idioma,
                vad_filter=True,
                beam_size=1,
                vad_parameters={"min_silence_duration_ms": 600},
            )
            segmentos_lista = list(segments)
        except Exception as e:
            self.on_status(f"Erro na transcrição: {e}")
            self._offset_seg += duracao
            return

        # BUG-02: escreve áudio em disco (WAV) em vez de acumular em RAM
        if self._wav:
            self._wav.writeframes((audio * 32767).astype(np.int16).tobytes())

        texto_completo = []
        for seg in segmentos_lista:
            texto = seg.text.strip()
            if not texto:
                continue
            start_abs = self._offset_seg + seg.start
            end_abs = self._offset_seg + seg.end
            if self.diarizar_ao_final:
                self._segmentos.append((start_abs, end_abs, texto))
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
        """Pós-processamento: separa falantes e escreve versão diarizada do .txt."""
        self.diarizando = True
        try:
            if not self._segmentos:
                self.on_status("Sem segmentos para diarizar.")
                return

            self.on_status("Iniciando separação de vozes (pós-processamento)...")
            try:
                from diarizador import diarizar

                # extrai áudio por trecho do WAV (não carrega tudo em RAM)
                trechos_audio = []
                if caminho_wav and os.path.isfile(caminho_wav):
                    for start, end, _t in self._segmentos:
                        trechos_audio.append(ler_trecho_wav(caminho_wav, start, end))
                else:
                    trechos_audio = [np.array([], dtype=np.float32)] * len(self._segmentos)

                perfil = None
                if self.identificar_voz:
                    from identificador_voz import carregar_perfil

                    perfil = carregar_perfil(ARQUIVO_PERFIL_VOZ)

                caminho_mic = getattr(self, "_caminho_wav_mic_salvo", None)
                vozes_conhecidas = {}
                if self.usar_vozes_conhecidas:
                    from identificador_voz import carregar_vozes_conhecidas

                    vozes_conhecidas = carregar_vozes_conhecidas(ARQUIVO_VOZES_CONHECIDAS)
                resultado, centroides = diarizar(
                    trechos_audio,
                    self._segmentos,
                    num_falantes=self.num_falantes,
                    on_status=self.on_status,
                    perfil_usuario=perfil,
                    limiar_identificacao=LIMIAR_IDENTIFICACAO_VOZ,
                    rotulo_usuario=self.rotulo_usuario,
                    identificar_ativo=self.identificar_voz,
                    caminho_mic_wav=caminho_mic,
                    limiar_rms_mic=LIMIAR_RMS_MIC,
                    eventos_meet=self.eventos_meet,
                    vozes_conhecidas=vozes_conhecidas,
                    retornar_centroides=True,
                )
                self._centroides_por_rotulo_ultima = centroides
            except Exception as e:
                self.on_status(f"Erro na diarização: {e}")
                logger.exception("Erro na diarização")
                return

            # escreve arquivo diarizado
            base = os.path.splitext(caminho_saida)[0]
            base, ext = os.path.splitext(caminho_saida)
            caminho_diar = f"{base}_diarizado{ext}"
            linhas = [
                f"=== Transcricao diarizada em {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n\n"
            ]
            for rotulo, start, end, texto in resultado:
                mm_ss_start = f"{int(start // 60):02d}:{int(start % 60):02d}"
                mm_ss_end = f"{int(end // 60):02d}:{int(end % 60):02d}"
                linhas.append(f"[{rotulo} {mm_ss_start}-{mm_ss_end}] {texto}\n")
            linhas.append("\n=== Fim ===\n")
            texto_diar = "".join(linhas)
            if self.criptografar:
                from crypto_storage import salvar_transcricao

                salvar_transcricao(caminho_diar, texto_diar)
            else:
                with open(caminho_diar, "w", encoding="utf-8") as f:
                    f.write(texto_diar)

            self.on_status(f"Diarização concluída: {os.path.basename(caminho_diar)}")
        finally:
            self.diarizando = False
            # FR-2.1: preserva áudio em PASTA_AUDIO (não apaga)
            self._preservar_audios(
                caminho_wav, getattr(self, "_caminho_wav_mic_salvo", None)
            )

    def _preservar_audios(self, *caminhos):
        """Move WAVs finalizados para PASTA_AUDIO e criptografa se ativo (FR-2.1/2.2)."""
        destinos = []
        os.makedirs(PASTA_AUDIO, exist_ok=True)
        from crypto_storage import criptografar_wav

        for caminho in caminhos:
            if not caminho or not os.path.isfile(caminho):
                continue
            try:
                destino = os.path.join(PASTA_AUDIO, os.path.basename(caminho))
                if os.path.abspath(caminho) != os.path.abspath(destino):
                    if os.path.isfile(destino):
                        os.remove(destino)
                    shutil.move(caminho, destino)
                destino = criptografar_wav(destino)
                destinos.append(destino)
            except Exception:
                logger.exception("Falha ao preservar áudio %s", caminho)
        return destinos

    def _checar_disco_livre(self):
        """FR-2.8: avisa se espaço livre < MIN_DISCO_LIVRE_GB (gravação segue)."""
        try:
            livre = shutil.disk_usage(self.pasta_saida).free
            limite = MIN_DISCO_LIVRE_GB * (1024**3)
            if livre < limite:
                self.on_status(
                    f"Aviso: pouco espaço em disco "
                    f"(menos de {MIN_DISCO_LIVRE_GB} GB livres). A gravação continua."
                )
        except Exception:
            logger.debug("Não foi possível checar espaço em disco", exc_info=True)

    def start(self):
        if self.rodando:
            return
        # FR-2.4: abre arquivos e captura ANTES do modelo — falha Whisper não perde áudio
        self._checar_disco_livre()
        self._abrir_arquivo()
        self._stop.clear()
        self._segmentos = []
        self._offset_seg = 0.0
        self.diarizando = False
        self._somente_audio = False
        self.rodando = True
        self._thread_cap = threading.Thread(target=self._capturar, daemon=True)
        self._thread_cap.start()
        if self.capturar_mic:
            self._thread_mic = threading.Thread(target=self._capturar_mic, daemon=True)
            self._thread_mic.start()
        try:
            self._carregar_modelo()
        except Exception as e:
            self._somente_audio = True
            self._modelo = None
            self.on_status(
                "Transcrição indisponível — gravando somente áudio para retranscrição"
            )
            logger.warning("Whisper indisponível; modo somente áudio: %s", e)
            # processador em modo só-gravação (sem transcrever)
            self._thread_proc = threading.Thread(target=self._processar_somente_audio, daemon=True)
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
        caminho = self._caminho_saida
        caminho_wav = self._caminho_wav
        self._caminho_wav_mic_salvo = self._caminho_wav_mic

        if self.diarizar_ao_final and self._segmentos and caminho:
            self._thread_diar = threading.Thread(
                target=self._rodar_diarizacao,
                args=(caminho, caminho_wav),
                daemon=True,
            )
            self._thread_diar.start()
        else:
            # FR-2.1: sem diarização (ou sem segmentos), move WAV imediatamente
            self._preservar_audios(caminho_wav, self._caminho_wav_mic_salvo)

        self._caminho_saida = None
        self.finalizando = False
        self.on_status("Transcrição encerrada.")
        return caminho

    # ---- métodos para o watchdog (T2.6) ----
    def _reiniciar_captura(self):
        """Reinicia a thread de captura se ela morrer."""
        if self.rodando and (self._thread_cap is None or not self._thread_cap.is_alive()):
            self.on_status("Reiniciando captura (watchdog)...")
            self._thread_cap = threading.Thread(target=self._capturar, daemon=True)
            self._thread_cap.start()

    def _reiniciar_processar(self):
        """Reinicia a thread de processamento se ela morrer."""
        if self.rodando and (self._thread_proc is None or not self._thread_proc.is_alive()):
            self.on_status("Reiniciando processamento (watchdog)...")
            self._thread_proc = threading.Thread(target=self._processar, daemon=True)
            self._thread_proc.start()

    def caminho_atual(self):
        return self._caminho_saida
