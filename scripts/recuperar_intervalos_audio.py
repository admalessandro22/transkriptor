#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai cópias de intervalos WAV sem alterar nem sobrescrever arquivos."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import wave
from pathlib import Path


BLOCO_FRAMES = 16_000
PADRAO_ROTULO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _abrir_wav_validado(caminho: Path):
    try:
        return wave.open(str(caminho), "rb")
    except (EOFError, wave.Error) as exc:
        raise ValueError("origem WAV inválida") from exc


def _frames_intervalo(wav, inicio_seg, fim_seg):
    try:
        inicio = float(inicio_seg)
        fim = float(fim_seg)
    except (TypeError, ValueError) as exc:
        raise ValueError("limites inválidos") from exc
    taxa = wav.getframerate()
    total = wav.getnframes()
    if taxa <= 0 or total <= 0:
        raise ValueError("origem WAV sem frames válidos")
    duracao_total = total / float(taxa)
    if not math.isfinite(inicio) or not math.isfinite(fim):
        raise ValueError("limites devem ser finitos")
    if inicio < 0 or fim <= inicio or fim > duracao_total:
        raise ValueError("intervalo fora da duração do WAV")
    frame_inicio = round(inicio * taxa)
    frame_fim = round(fim * taxa)
    if frame_inicio < 0 or frame_fim > total or frame_fim <= frame_inicio:
        raise ValueError("intervalo não contém frames válidos")
    return frame_inicio, frame_fim


def _copiar_frames(origem, arquivo_destino, frame_inicio, frames_total):
    bytes_por_frame = origem.getnchannels() * origem.getsampwidth()
    if bytes_por_frame <= 0:
        raise ValueError("formato WAV inválido")
    origem.setpos(frame_inicio)
    restantes = frames_total
    with wave.open(arquivo_destino, "wb") as destino:
        destino.setparams(origem.getparams())
        while restantes:
            solicitados = min(BLOCO_FRAMES, restantes)
            dados = origem.readframes(solicitados)
            if not dados or len(dados) % bytes_por_frame:
                raise ValueError("WAV terminou antes do intervalo solicitado")
            copiados = len(dados) // bytes_por_frame
            destino.writeframesraw(dados)
            restantes -= copiados


def _validar_saida(caminho: Path, frames: int, sample_rate: int) -> None:
    with _abrir_wav_validado(caminho) as wav:
        if wav.getnframes() != frames or wav.getframerate() != sample_rate:
            raise ValueError("WAV extraído falhou na validação")


def extrair_intervalo(origem, destino, inicio_seg, fim_seg) -> dict:
    """Cria um WAV novo por streaming e prova que a origem não mudou."""
    origem_path = Path(origem).expanduser().resolve(strict=True)
    if not origem_path.is_file():
        raise ValueError("origem deve ser arquivo")
    destino_path = Path(destino).expanduser().resolve(strict=False)
    if destino_path.exists() or destino_path.is_symlink():
        raise FileExistsError(destino_path)
    if destino_path == origem_path:
        raise FileExistsError(destino_path)

    hash_antes = _sha256(origem_path)
    try:
        wav_origem = _abrir_wav_validado(origem_path)
        with wav_origem as wav:
            frame_inicio, frame_fim = _frames_intervalo(wav, inicio_seg, fim_seg)
            frames = frame_fim - frame_inicio
            taxa = wav.getframerate()
            destino_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporario_nome = tempfile.mkstemp(
                prefix=f".{destino_path.name}.",
                suffix=".part",
                dir=str(destino_path.parent),
            )
            try:
                with os.fdopen(fd, "w+b") as temporario:
                    _copiar_frames(wav, temporario, frame_inicio, frames)
                    temporario.flush()
                    os.fsync(temporario.fileno())
                temporario_path = Path(temporario_nome)
                _validar_saida(temporario_path, frames, taxa)
                hash_depois = _sha256(origem_path)
                if hash_depois != hash_antes:
                    raise RuntimeError("origem mudou durante a extração")
                os.link(temporario_path, destino_path)
            finally:
                Path(temporario_nome).unlink(missing_ok=True)
    except (EOFError, wave.Error) as exc:
        raise ValueError("origem WAV inválida") from exc

    return {
        "origem": str(origem_path),
        "destino": str(destino_path),
        "frames": frames,
        "sample_rate": taxa,
        "duracao_seg": frames / float(taxa),
        "sha256_original_antes": hash_antes,
        "sha256_original_depois": hash_depois,
        "sha256_destino": _sha256(destino_path),
    }


def _parse_intervalo(valor: str):
    partes = valor.split(":")
    if len(partes) != 3 or not PADRAO_ROTULO.fullmatch(partes[0]):
        raise argparse.ArgumentTypeError("use ROTULO:INICIO:FIM")
    try:
        return partes[0], float(partes[1]), float(partes[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("início e fim devem ser números") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Recupera intervalos de um WAV")
    parser.add_argument("--origem", required=True)
    parser.add_argument("--destino", required=True)
    parser.add_argument(
        "--intervalo", required=True, action="append", type=_parse_intervalo
    )
    args = parser.parse_args(argv)
    pasta = Path(args.destino).expanduser().resolve(strict=False)
    if pasta.exists() and not pasta.is_dir():
        parser.error("destino deve ser uma pasta")
    alvos = [pasta / f"{rotulo}.wav" for rotulo, _i, _f in args.intervalo]
    if len(set(alvos)) != len(alvos) or any(alvo.exists() for alvo in alvos):
        parser.error("destinos repetidos ou já existentes")
    resultados = []
    for (rotulo, inicio, fim), alvo in zip(args.intervalo, alvos):
        info = extrair_intervalo(args.origem, alvo, inicio, fim)
        resultados.append({"rotulo": rotulo, **info})
    print(json.dumps(resultados, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
