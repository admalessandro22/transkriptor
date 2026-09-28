# -*- coding: utf-8 -*-
"""Índice paginado de reuniões sem abrir conteúdo (T-13.D7)."""
from __future__ import annotations

import hashlib
import json
import os
import re
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
    arquivo: str | None = None


VERSAO_INDICE = 1
_NOME_COM_DATA = re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})h(\d{2})")
_SUFIXO_MANIFESTO = ".resultado.json"


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


def _metadados_do_job(raiz: Path, meeting_id: str) -> dict:
    """Título/início/duração que a gravação deixou no job (sem conteúdo de fala)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(meeting_id)):
        return {}
    caminho = raiz / ".jobs_processamento" / f"{meeting_id}.json"
    try:
        metadados = json.loads(caminho.read_text(encoding="utf-8")).get("metadados") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    info = {}
    titulo = metadados.get("titulo_reuniao")
    if isinstance(titulo, str) and titulo.strip():
        info["title"] = titulo.strip()[:80]
    inicio = metadados.get("inicio_iso")
    if isinstance(inicio, str) and inicio:
        info["started_at"] = inicio
    duracao = metadados.get("duracao_seg")
    if isinstance(duracao, (int, float)) and not isinstance(duracao, bool) and duracao >= 0:
        info["duration_ms"] = int(round(float(duracao) * 1000))
    return info


def _inicio_pelo_nome(nome_manifesto: str) -> str | None:
    """`transcricao_2026-09-22_13h59...` -> horário local de início da gravação."""
    m = _NOME_COM_DATA.search(nome_manifesto)
    if not m:
        return None
    ano, mes, dia, hora, minuto = m.groups()
    return f"{ano}-{mes}-{dia}T{hora}:{minuto}:00"


def _completar_resumo(resumo: dict, caminho: Path, meeting_id: str, anterior: dict | None) -> dict:
    """Job > nome do arquivo > índice anterior; o horário de processamento é o último recurso."""
    info = _metadados_do_job(caminho.parent, meeting_id)
    anterior = anterior if isinstance(anterior, dict) else {}
    resumo = dict(resumo)
    resumo["title"] = info.get("title") or anterior.get("title")
    resumo["duration_ms"] = info.get("duration_ms", anterior.get("duration_ms"))
    resumo["started_at"] = (
        info.get("started_at")
        or anterior.get("inicio_real")
        or _inicio_pelo_nome(caminho.name)
        or resumo["started_at"]
    )
    if info.get("started_at") or anterior.get("inicio_real"):
        resumo["inicio_real"] = resumo["started_at"]
    if anterior.get("titulo_usuario"):
        resumo["titulo_usuario"] = anterior["titulo_usuario"]
    return resumo


def _varrer_manifestos(raiz: Path) -> dict[str, Path]:
    achados: dict[str, Path] = {}
    if not raiz.is_dir():
        return achados
    for caminho in sorted(raiz.rglob("*.resultado.json")):
        if any(parte.startswith(".lixeira") for parte in caminho.relative_to(raiz).parts):
            continue  # reunião em exclusão (exclusao_reuniao.LIXEIRA)
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
    resumo = _completar_resumo(
        _resumo_de_manifesto(atual), caminho, str(manifesto.meeting_id), reunioes.get(str(manifesto.meeting_id))
    )
    reunioes[str(manifesto.meeting_id)] = {
        "manifest": caminho.name,
        "sha": _sha_arquivo(caminho),
        "mtime_ns": caminho.stat().st_mtime_ns,
        "confirmado": True,
        **resumo,
    }
    _salvar_indice(indice, reunioes)


def definir_titulo(index_path: Path, meeting_id: str, titulo: str) -> str | None:
    """Título escolhido pelo usuário (≤ 80); vazio volta ao título da gravação."""
    limpo = re.sub(r"\s+", " ", str(titulo or "")).strip()
    limpo = "".join(ch for ch in limpo if ch.isprintable())
    if len(limpo) > 80:
        raise ValueError("título acima de 80 caracteres")
    indice = Path(index_path)
    reunioes = _carregar_indice(indice)
    entrada = reunioes.get(str(meeting_id))
    if not isinstance(entrada, dict):
        raise KeyError("reunião não encontrada no índice")
    if limpo:
        entrada["titulo_usuario"] = limpo
    else:
        entrada.pop("titulo_usuario", None)
    _salvar_indice(indice, reunioes)
    return limpo or None


def _instante(iso: object) -> float:
    """ISO com fuso (job, manifesto) ou sem fuso (hora local do nome do arquivo)."""
    import datetime as _dt

    try:
        texto = str(iso).strip()
        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"
        return _dt.datetime.fromisoformat(texto).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _arquivo_base(manifesto: object) -> str | None:
    """Nome-base da transcrição (casa com `/api/transcricoes` no Assistente)."""
    if isinstance(manifesto, str) and manifesto.endswith(_SUFIXO_MANIFESTO):
        return manifesto[: -len(_SUFIXO_MANIFESTO)]
    return None


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
                resumo = _completar_resumo(
                    _resumo_de_manifesto(carregar_manifesto(caminho)), caminho, mid, entrada
                )
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
    # Mais recente primeiro; empate por id crescente mantém o cursor estável.
    ordenados = sorted(
        sorted(reunioes),
        key=lambda mid: _instante(reunioes[mid].get("started_at") if isinstance(reunioes[mid], dict) else None),
        reverse=True,
    )
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
                title=entrada.get("titulo_usuario") or entrada.get("title"),
                started_at=str(entrada.get("started_at", "")),
                duration_ms=entrada.get("duration_ms"),
                revision=f"v{entrada.get('schema_version', 1)}-{str(entrada.get('sha', ''))[:8]}",
                quality_state="desatualizado"
                if not entrada.get("confirmado", True)
                else str(entrada.get("quality", "parcial")),
                arquivo=_arquivo_base(entrada.get("manifest")),
            )
        )
    proximo = fatia[-1] if inicio + limit < len(ordenados) else None
    return tuple(summaries), proximo
