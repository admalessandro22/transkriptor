# -*- coding: utf-8 -*-
"""Retranscrição offline de áudios retidos (FR-2.5)."""
from __future__ import annotations

import datetime
import logging
import math
import os
import re
import tempfile
import wave
from pathlib import Path

import numpy as np

from config import CHUNK_SEGUNDOS, PASTA_AUDIO, PASTA_TRANSCRICOES, SAMPLE_RATE
from transcricao_core import Transcritor

logger = logging.getLogger(__name__)


def _ler_audio_pcm(caminho: str) -> tuple[np.ndarray, int]:
    """Retorna (float32 mono, sample_rate) de .wav ou .wav.enc."""
    path = Path(caminho)
    if not path.is_file():
        raise FileNotFoundError(caminho)
    tmp_wav = None
    try:
        if path.name.lower().endswith(".wav.enc"):
            from crypto_storage import ler_bytes_arquivo

            plano = ler_bytes_arquivo(str(path))
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            Path(tmp_wav).write_bytes(plano)
            wav_path = tmp_wav
        else:
            wav_path = str(path)
        with wave.open(wav_path, "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            sw = w.getsampwidth()
            frames = w.readframes(w.getnframes())
        if sw == 2:
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
        else:
            data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        if nch > 1:
            data = data.reshape(-1, nch).mean(axis=1)
        return data, sr
    finally:
        if tmp_wav and os.path.isfile(tmp_wav):
            try:
                os.remove(tmp_wav)
            except OSError:
                pass


def listar_audios(pasta_audio: str | None = None) -> list[dict]:
    """Lista áudios em PASTA_AUDIO com data e duração (header WAV)."""
    pasta = Path(pasta_audio or PASTA_AUDIO)
    if not pasta.is_dir():
        return []
    items = []
    for path in sorted(pasta.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        nome = path.name.lower()
        if not (nome.endswith(".wav") or nome.endswith(".wav.enc")):
            continue
        dur = 0.0
        try:
            if nome.endswith(".wav.enc"):
                from crypto_storage import ler_bytes_arquivo

                plano = ler_bytes_arquivo(str(path))
                # header WAV: sample rate em bytes 24-28, data size em 40-44
                if len(plano) >= 44 and plano[:4] == b"RIFF":
                    sr = struct_unpack_sr(plano)
                    # data chunk size approx
                    nframes = max(0, (len(plano) - 44) // 2)
                    dur = nframes / float(sr or SAMPLE_RATE)
            else:
                with wave.open(str(path), "rb") as w:
                    dur = w.getnframes() / float(w.getframerate() or SAMPLE_RATE)
        except Exception:
            logger.debug("Não foi possível ler duração de %s", path.name, exc_info=True)
        mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
        items.append(
            {
                "caminho": str(path),
                "nome": path.name,
                "duracao_seg": dur,
                "mtime": mtime,
                "rotulo": f"{mtime:%d/%m/%Y %H:%M} — {dur:.0f}s — {path.name}",
            }
        )
    return items


def struct_unpack_sr(plano: bytes) -> int:
    import struct

    return struct.unpack_from("<I", plano, 24)[0]


PADRAO_BASE_SAIDA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")


def _timestamp_relativo(segundos: float) -> str:
    total = max(0, int(segundos))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _duracao_legivel(segundos: float) -> str:
    return _timestamp_relativo(segundos)


def _escrever_texto_atomico(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{caminho.stem}_", suffix=".tmp", dir=str(caminho.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario and os.path.isfile(temporario):
            try:
                os.remove(temporario)
            except OSError:
                pass


def _carregar_modelo(modelo_whisper, pasta: str, on_status, modelo_nome=None):
    if modelo_whisper is not None:
        return modelo_whisper
    transcritor = Transcritor(
        modelo=modelo_nome,
        pasta_saida=pasta,
        capturar_mic=False,
        diarizar_ao_final=False,
        criptografar=False,
        on_status=on_status,
    )
    transcritor._carregar_modelo()
    return transcritor._modelo


def _texto_transcricao(linhas: list[str], metadados: dict, duracao: float) -> str:
    inicio = metadados.get("inicio_iso") or datetime.datetime.now().astimezone().isoformat()
    fim = metadados.get("fim_iso") or "não informado"
    origem = str(metadados.get("origem") or "reunião")
    cabecalho = [
        "=== Transcricao da reuniao ===",
        f"Inicio: {inicio}",
        f"Fim: {fim}",
        f"Duracao: {_duracao_legivel(float(metadados.get('duracao_seg', duracao)))}",
        f"Origem: {origem}",
    ]
    try:
        lacuna = float(metadados.get("lacuna_estimada_seg") or 0)
    except (TypeError, ValueError):
        lacuna = 0
    if math.isfinite(lacuna) and lacuna > 0:
        valor = int(lacuna) if lacuna.is_integer() else round(lacuna, 3)
        cabecalho.append(
            f"AVISO DE INTEGRIDADE: lacuna estimada de {valor} s no áudio desta reunião."
        )
    cabecalho.append("")
    if not linhas:
        linhas = ["[00:00:00] (nenhuma fala reconhecida)"]
    return "\n".join(cabecalho + linhas + ["", "=== Fim ===", ""])


def retranscrever(
    caminho_audio: str,
    *,
    pasta_saida: str | None = None,
    nome_base_saida: str | None = None,
    modelo_whisper=None,
    modelo_nome: str | None = None,
    idioma: str = "pt",
    diarizar: bool = True,
    chunk: float = CHUNK_SEGUNDOS,
    gerar_copia_tkpt: bool = False,
    metadados: dict | None = None,
    caminho_mic: str | None = None,
    criptografar: bool | None = None,
    on_status=None,
    identificar_voz: bool = False,
    usar_vozes_conhecidas: bool = True,
    **_kwargs,
) -> str:
    """Transcreve áudio retido e entrega `.txt` UTF-8 atômico como principal."""
    from crypto_storage import nome_base_transcricao

    on_status = on_status or (lambda _m: None)
    pasta = str(Path(pasta_saida or PASTA_TRANSCRICOES).resolve())
    os.makedirs(pasta, exist_ok=True)
    base = nome_base_saida or nome_base_transcricao()
    if not PADRAO_BASE_SAIDA.fullmatch(str(base)):
        raise ValueError("nome base de saída inválido")
    if criptografar is not None:
        gerar_copia_tkpt = gerar_copia_tkpt or bool(criptografar)

    audio, sr = _ler_audio_pcm(caminho_audio)
    if sr != SAMPLE_RATE and audio.size:
        n_out = int(audio.size * SAMPLE_RATE / sr)
        x_old = np.linspace(0, 1, num=audio.size, endpoint=False)
        x_new = np.linspace(0, 1, num=n_out, endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)

    modelo = _carregar_modelo(modelo_whisper, pasta, on_status, modelo_nome)
    tamanho_bloco = max(SAMPLE_RATE, int(SAMPLE_RATE * chunk))
    linhas, segmentos = [], []
    for inicio_frame in range(0, audio.size, tamanho_bloco):
        fim_frame = min(audio.size, inicio_frame + tamanho_bloco)
        pedaco = audio[inicio_frame:fim_frame]
        inicio_bloco = inicio_frame / SAMPLE_RATE
        encontrados, _info = modelo.transcribe(
            pedaco,
            language=None if idioma == "auto" else idioma,
            vad_filter=True,
            beam_size=1,
            vad_parameters={"min_silence_duration_ms": 600},
        )
        for segmento in list(encontrados):
            texto = str(segmento.text).strip()
            if not texto:
                continue
            inicio_abs = inicio_bloco + float(segmento.start)
            fim_abs = inicio_bloco + float(segmento.end)
            linhas.append(f"[{_timestamp_relativo(inicio_abs)}] {texto}")
            segmentos.append((inicio_abs, fim_abs, texto))

    metadados = dict(metadados or {})
    duracao = audio.size / float(SAMPLE_RATE)
    texto_final = _texto_transcricao(linhas, metadados, duracao)
    caminho_final = Path(pasta) / f"{base}.txt"
    _escrever_texto_atomico(caminho_final, texto_final)

    if diarizar and segmentos:
        with tempfile.TemporaryDirectory(prefix="diarizacao_", dir=pasta) as tmp_dir:
            temporario_txt = Path(tmp_dir) / f"{base}.txt"
            temporario_wav = Path(tmp_dir) / f"{base}_audio.wav"
            temporario_txt.write_text(texto_final, encoding="utf-8")
            with wave.open(str(temporario_wav), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes((audio * 32767).astype(np.int16).tobytes())
            transcritor = Transcritor(
                pasta_saida=tmp_dir,
                diarizar_ao_final=True,
                capturar_mic=False,
                identificar_voz=identificar_voz,
                usar_vozes_conhecidas=usar_vozes_conhecidas,
                criptografar=False,
                on_status=on_status,
            )
            transcritor._segmentos = segmentos
            transcritor._caminho_wav_mic_salvo = caminho_mic
            transcritor._preservar_audios = lambda *_caminhos: []
            transcritor._rodar_diarizacao(str(temporario_txt), str(temporario_wav))
            temporario_diar = Path(tmp_dir) / f"{base}_diarizado.txt"
            if temporario_diar.is_file():
                _escrever_texto_atomico(
                    Path(pasta) / temporario_diar.name,
                    temporario_diar.read_text(encoding="utf-8"),
                )

    if gerar_copia_tkpt:
        try:
            from crypto_storage import salvar_transcricao

            salvar_transcricao(str(caminho_final.with_suffix(".tkpt")), texto_final)
        except Exception as exc:  # o TXT principal nunca é removido por esta falha
            logger.warning("Cópia TKPT indisponível (%s)", type(exc).__name__)

    on_status(f"Retranscrição concluída: {caminho_final.name}")
    return str(caminho_final)
