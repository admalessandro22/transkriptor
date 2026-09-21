# -*- coding: utf-8 -*-
"""Índice paginado de reuniões sem abrir conteúdo (T-13.D7)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class MeetingSummary:
    meeting_id: str
    title: str | None
    started_at: str
    duration_ms: int | None
    revision: str
    quality_state: str


VERSAO_INDICE = 1


def _sha_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _carregar_indice(caminho: Path) -> dict:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict) or dados.get("version") != VERSAO_INDICE:
        return {}
    reunioes = dados.get("meetings")
    return reunioes if isinstance(reunioes, dict) else {}


def _salvar_indice(caminho: Path, reunioes: dict) -> None:
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{destino.stem}_", suffix=".tmp", dir=str(destino.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(
                {"version": VERSAO_INDICE, "meetings": reunioes},
                arquivo,
                ensure_ascii=False,
                sort_keys=True,
            )
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    finally:
        try:
            if os.path.isfile(temporario):
                os.remove(temporario)
        except OSError:
            pass


def _resumo_de_manifesto(manifesto) -> dict:
    from resultado_reuniao import StageState

    estados = {
        str(e.value if isinstance(e, StageState) else e)
        for e in manifesto.stage_status.values()
    }
    if "failed" in estados:
        qualidade = "falhou"
    elif estados and estados == {"complete"}:
        qualidade = "pronto"
    else:
        qualidade = "parcial"
    return {
        "title": None,
        "started_at": str(manifesto.created_at),
        "duration_ms": None,
        "quality": qualidade,
        "schema_version": int(manifesto.schema_version),
    }


def _varrer_manifestos(raiz: Path) -> dict[str, Path]:
    achados: dict[str, Path] = {}
    if not raiz.is_dir():
        return achados
    for caminho in sorted(raiz.rglob("*.resultado.json")):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        mid = dados.get("meeting_id")
        if not isinstance(mid, str) or not mid:
            continue
        anterior = achados.get(mid)
        try:
            if anterior is None or caminho.stat().st_mtime_ns >= anterior.stat().st_mtime_ns:
                achados[mid] = caminho
        except OSError:
            continue
    return achados


def atualizar_indice(index_path: Path, manifesto) -> None:
    """Confirma o manifesto como versão vigente da reunião no índice."""
    from resultado_reuniao import carregar_manifesto

    indice = Path(index_path)
    reunioes = _carregar_indice(indice)
    achados = _varrer_manifestos(indice.parent)
    caminho = achados.get(str(manifesto.meeting_id))
    if caminho is None:
        raise ValueError("manifesto não encontrado para a reunião")
    atual = carregar_manifesto(caminho)
    resumo = _resumo_de_manifesto(atual)
    reunioes[str(manifesto.meeting_id)] = {
        "manifest": caminho.name,
        "sha": _sha_arquivo(caminho),
        "mtime_ns": caminho.stat().st_mtime_ns,
        "confirmado": True,
        **resumo,
    }
    _salvar_indice(indice, reunioes)


def listar_reunioes(index_path: Path, *, cursor: str | None, limit: int):
    """Lista sem abrir TXT/descriptografar; só manifests (metadados)."""
    from resultado_reuniao import carregar_manifesto

    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit permitido: 1–100")
    indice = Path(index_path)
    reunioes = _carregar_indice(indice)
    achados = _varrer_manifestos(indice.parent)
    mudancas = False
    for mid, caminho in achados.items():
        try:
            mtime = caminho.stat().st_mtime_ns
        except OSError:
            continue
        entrada = reunioes.get(mid)
        if (
            isinstance(entrada, dict)
            and entrada.get("manifest") == caminho.name
            and entrada.get("mtime_ns") == mtime
        ):
            continue
        try:
            sha = _sha_arquivo(caminho)
        except OSError:
            continue
        if (
            not isinstance(entrada, dict)
            or entrada.get("sha") != sha
            or entrada.get("manifest") != caminho.name
        ):
            primeiro_avistamento = not isinstance(entrada, dict)
            try:
                resumo = _resumo_de_manifesto(carregar_manifesto(caminho))
            except ValueError:
                continue
            reunioes[mid] = {
                "manifest": caminho.name,
                "sha": sha,
                "mtime_ns": mtime,
                "confirmado": primeiro_avistamento,
                **resumo,
            }
            mudancas = True
    if mudancas:
        _salvar_indice(indice, reunioes)
    ordenados = sorted(reunioes)
    inicio = 0
    if cursor is not None:
        if cursor not in ordenados:
            raise ValueError("cursor inválido")
        inicio = ordenados.index(cursor) + 1
    fatia = ordenados[inicio : inicio + limit]
    summaries = []
    for mid in fatia:
        entrada = reunioes[mid]
        summaries.append(
            MeetingSummary(
                meeting_id=mid,
                title=entrada.get("title"),
                started_at=str(entrada.get("started_at", "")),
                duration_ms=entrada.get("duration_ms"),
                revision=f"v{entrada.get('schema_version', 1)}-{str(entrada.get('sha', ''))[:8]}",
                quality_state="desatualizado"
                if not entrada.get("confirmado", True)
                else str(entrada.get("quality", "parcial")),
            )
        )
    proximo = fatia[-1] if inicio + limit < len(ordenados) else None
    return tuple(summaries), proximo
