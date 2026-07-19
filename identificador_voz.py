# -*- coding: utf-8 -*-
"""Identificação da voz do usuário — perfil, similaridade e matching."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from config import LIMIAR_IDENTIFICACAO_VOZ


def similaridade_cosseno(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    na = np.linalg.norm(a) + 1e-9
    nb = np.linalg.norm(b) + 1e-9
    return float(np.dot(a, b) / (na * nb))


def _usar_criptografia_voz() -> bool:
    try:
        from crypto_storage import chave_disponivel, criptografia_ativa

        return criptografia_ativa() and chave_disponivel()
    except Exception:
        return False


def salvar_perfil(embedding: np.ndarray, path, path_enc=None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path_enc is None:
        path_enc = path.with_suffix(".enc")
    if _usar_criptografia_voz():
        from io import BytesIO

        from crypto_storage import salvar_bytes_arquivo

        buf = BytesIO()
        np.savez(buf, embedding=embedding.astype(np.float32), versao=np.int32(1))
        salvar_bytes_arquivo(str(path_enc), buf.getvalue())
        if path.is_file():
            path.unlink()
        return
    np.savez(
        path,
        embedding=embedding.astype(np.float32),
        versao=np.int32(1),
    )


def carregar_perfil(path, path_enc=None) -> np.ndarray | None:
    path = Path(path)
    if path_enc is None:
        path_enc = path.with_suffix(".enc")
    path_enc = Path(path_enc)
    if path_enc.is_file():
        try:
            from io import BytesIO

            from crypto_storage import ler_bytes_arquivo

            raw = ler_bytes_arquivo(str(path_enc))
            data = np.load(BytesIO(raw))
            return data["embedding"]
        except Exception:
            return None
    if not path.is_file():
        return None
    try:
        data = np.load(path)
        return data["embedding"]
    except Exception:
        return None


def media_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    if not embeddings:
        raise ValueError("lista de embeddings vazia")
    stack = np.stack([e.astype(np.float32) for e in embeddings], axis=0)
    return stack.mean(axis=0).astype(np.float32)


def identificar_cluster(
    centroides: list[np.ndarray],
    perfil: np.ndarray,
    limiar: float = LIMIAR_IDENTIFICACAO_VOZ,
) -> int | None:
    melhor_idx = None
    melhor_sim = -1.0
    for i, centroide in enumerate(centroides):
        sim = similaridade_cosseno(centroide, perfil)
        if sim > melhor_sim:
            melhor_sim = sim
            melhor_idx = i
    if melhor_idx is None or melhor_sim < limiar:
        return None
    return melhor_idx


def extrair_embedding_perfil(encoder, audio: np.ndarray) -> np.ndarray | None:
    """Extrai embedding de um trecho float32 mono 16kHz."""
    from diarizador import _extrair_embedding

    return _extrair_embedding(encoder, audio)


def gravar_audio_microfone(duracao_seg: float, sample_rate: int = 16000) -> list[np.ndarray]:
    """Grava chunks do microfone padrão por duracao_seg segundos."""
    import time

    import soundcard as sc

    mic = sc.default_microphone()
    frames = int(sample_rate * 0.5)
    chunks: list[np.ndarray] = []
    deadline = time.monotonic() + duracao_seg
    with mic.recorder(samplerate=sample_rate, channels=1) as rec:
        while time.monotonic() < deadline:
            data = rec.record(numframes=frames)
            if data.ndim > 1:
                data = data.mean(axis=1)
            chunks.append(data.astype(np.float32))
    return chunks


def perfil_de_chunks(encoder, chunks: list[np.ndarray]) -> np.ndarray | None:
    embeddings = []
    for chunk in chunks:
        emb = extrair_embedding_perfil(encoder, chunk)
        if emb is not None:
            embeddings.append(emb)
    if not embeddings:
        return None
    return media_embeddings(embeddings)


def _embedding_para_json(embedding: np.ndarray) -> list[float]:
    return embedding.astype(np.float32).tolist()


def carregar_vozes_conhecidas(arquivo, arquivo_enc=None) -> dict:
    """Carrega banco local de vozes renomeadas (FR-8.5)."""
    path = Path(arquivo)
    if arquivo_enc is None:
        arquivo_enc = path.with_suffix(".enc")
    path_enc = Path(arquivo_enc)
    dados = None
    if path_enc.is_file():
        try:
            from crypto_storage import ler_bytes_arquivo

            dados = json.loads(ler_bytes_arquivo(str(path_enc)).decode("utf-8"))
        except Exception:
            return {}
    elif path.is_file():
        try:
            with open(path, encoding="utf-8") as f:
                dados = json.load(f)
        except Exception:
            return {}
    else:
        return {}
    if dados is None:
        return {}
    if not isinstance(dados, dict):
        return {}
    for info in dados.values():
        if isinstance(info, dict) and "embedding" in info:
            info["embedding"] = np.asarray(info["embedding"], dtype=np.float32)
    return dados


def salvar_voz_conhecida(
    nome: str,
    embedding: np.ndarray,
    arquivo,
    rotulo_origem: str | None = None,
) -> None:
    path = Path(arquivo)
    vozes = carregar_vozes_conhecidas(path)
    vozes[nome] = {
        "rotulo_origem": rotulo_origem,
        "embedding": _embedding_para_json(embedding),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    serializado = {
        chave: {
            "rotulo_origem": info.get("rotulo_origem"),
            "embedding": (
                info["embedding"].tolist()
                if isinstance(info.get("embedding"), np.ndarray)
                else info.get("embedding")
            ),
        }
        for chave, info in vozes.items()
    }
    if _usar_criptografia_voz():
        from crypto_storage import salvar_bytes_arquivo

        path_enc = path.with_suffix(".enc")
        salvar_bytes_arquivo(
            str(path_enc),
            json.dumps(serializado, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        if path.is_file():
            path.unlink()
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializado, f, ensure_ascii=False, indent=2)


def renomear_falante(
    rotulo_origem: str,
    novo_nome: str,
    embedding: np.ndarray,
    arquivo,
) -> None:
    salvar_voz_conhecida(novo_nome, embedding, arquivo, rotulo_origem=rotulo_origem)