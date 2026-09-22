# -*- coding: utf-8 -*-
"""Resultado estruturado canônico: JSON + TXT exato, correção e undo (T-13.D7).

Extraído de `resultado_reuniao.py` para o limite de 500 linhas.
Correção nunca cadastra biometria (ação separada e revogável).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


NOME_PENDENTE = "Identificação pendente"
VERSAO_SEGMENTOS = 1


@dataclass(frozen=True)
class SegmentoResultado:
    segment_id: str
    start_ms: int
    end_ms: int
    audio_source: str
    text: str
    speaker_cluster_id: str
    overlap: bool = False
    assignment: Mapping[str, object] | None = None


def _hora_curta(ms: int) -> str:
    total = max(0, int(ms) // 1000)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_segment_txt(start_ms: int, display_name: str | None, text: str) -> str:
    """Uma linha por segmento: `[HH:MM:SS] Nome: texto`.

    Sem atribuição qualificada, `Nome` é literalmente `Identificação pendente`;
    ids internos (`FALANTE_00`) nunca vazam na exportação nominal.
    """
    nome = (display_name or "").strip()
    if not nome or nome.startswith("FALANTE_"):
        nome = NOME_PENDENTE
    return f"[{_hora_curta(int(start_ms))}] {nome}: {(text or '').strip()}"


def _validar_nome_correcao(display_name: str) -> str:
    nome = (display_name or "").strip()
    if not nome or len(nome) > 80:
        raise ValueError("nome de correção inválido")
    if nome.startswith("FALANTE_"):
        raise ValueError("correção não aceita id interno")
    return nome


def _escrever_json_atomico(caminho: Path, dados: dict) -> None:
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{destino.stem}_", suffix=".tmp", dir=str(destino.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, sort_keys=True)
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


def salvar_segmentos(
    path: Path,
    segmentos: Sequence[SegmentoResultado | Mapping],
    mapeamento: Mapping | None = None,
) -> str:
    """Persiste segmentos + mapeamento cluster→participante. Devolve `rev-1`."""
    serializados = []
    for seg in segmentos:
        if isinstance(seg, SegmentoResultado):
            serializados.append(
                {
                    "segment_id": seg.segment_id,
                    "start_ms": int(seg.start_ms),
                    "end_ms": int(seg.end_ms),
                    "audio_source": str(seg.audio_source),
                    "text": str(seg.text),
                    "speaker_cluster_id": str(seg.speaker_cluster_id),
                    "overlap": bool(seg.overlap),
                    "assignment": dict(seg.assignment) if seg.assignment is not None else None,
                }
            )
        else:
            serializados.append(
                {
                    "segment_id": str(seg["segment_id"]),
                    "start_ms": int(seg["start_ms"]),
                    "end_ms": int(seg["end_ms"]),
                    "audio_source": str(seg.get("audio_source", "loopback")),
                    "text": str(seg.get("text", "")),
                    "speaker_cluster_id": str(seg.get("speaker_cluster_id", "")),
                    "overlap": bool(seg.get("overlap", False)),
                    "assignment": dict(seg["assignment"]) if seg.get("assignment") is not None else None,
                }
            )
    dados = {
        "schema_version": VERSAO_SEGMENTOS,
        "revision": "rev-1",
        "segmentos": serializados,
        "mapeamento": dict(mapeamento or {}),
        "historico": [],
    }
    _escrever_json_atomico(Path(path), dados)
    return "rev-1"


def carregar_segmentos(path: Path) -> dict:
    dados = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(dados, dict) or dados.get("schema_version") != VERSAO_SEGMENTOS:
        raise ValueError("resultado estruturado inválido")
    if not isinstance(dados.get("segmentos"), list) or not isinstance(
        dados.get("revision"), str
    ):
        raise ValueError("resultado estruturado inválido")
    for seg in dados["segmentos"]:
        if not isinstance(seg, dict) or not all(
            chave in seg for chave in (
                "segment_id", "start_ms", "end_ms", "audio_source", "text", "speaker_cluster_id"
            )
        ):
            raise ValueError("segmento estruturado inválido")
        if (
            not isinstance(seg["segment_id"], str) or not seg["segment_id"]
            or type(seg["start_ms"]) is not int or type(seg["end_ms"]) is not int
            or seg["start_ms"] < 0 or seg["end_ms"] <= seg["start_ms"]
            or seg["audio_source"] not in ("loopback", "microphone")
            or not isinstance(seg["text"], str)
            or not isinstance(seg["speaker_cluster_id"], str)
            or (seg.get("assignment") is not None and not isinstance(seg["assignment"], dict))
        ):
            raise ValueError("segmento estruturado inválido")
    dados.setdefault("mapeamento", {})
    dados.setdefault("historico", [])
    return dados


def _nome_para_cluster(mapeamento: Mapping, cluster: str) -> str | None:
    entrada = (mapeamento or {}).get(cluster)
    if not isinstance(entrada, dict):
        return None
    nome = entrada.get("display_name")
    return str(nome) if isinstance(nome, str) and nome else None


def exportar_txt(segmentos: Sequence[Mapping], mapeamento: Mapping) -> str:
    """TXT derivado do canônico: mesma ordem, texto, tempo e nome."""
    linhas = [
        format_segment_txt(
            int(seg["start_ms"]),
            _nome_para_cluster(mapeamento, str(seg.get("speaker_cluster_id", ""))),
            str(seg.get("text", "")),
        )
        for seg in segmentos
    ]
    return "\n".join(linhas) + ("\n" if linhas else "")


def aplicar_correcao(
    path: Path,
    *,
    expected_revision: str,
    speaker_cluster_id: str,
    participant_id: str | None,
    display_name: str,
    autor: str = "local",
) -> str:
    """Corrige o mapeamento da reunião (nova revisão imutável + undo).

    Exige `expected_revision` (edição concorrente é recusada); nunca cadastra
    biometria. Devolve a nova revisão.
    """
    dados = carregar_segmentos(path)
    if dados["revision"] != expected_revision:
        raise ValueError("revisão esperada divergente; recarregue a reunião")
    cluster = str(speaker_cluster_id)
    if not cluster:
        raise ValueError("cluster inválido")
    nome = _validar_nome_correcao(display_name)
    anterior = dados["mapeamento"].get(cluster)
    numero = len(dados["historico"]) + 2
    nova_revisao = f"rev-{numero}"
    dados["mapeamento"][cluster] = {
        "participant_id": participant_id,
        "display_name": nome,
        "origem": "manual",
        "autor": str(autor),
    }
    dados["historico"].append(
        {
            "revision": nova_revisao,
            "acao": "corrigir",
            "cluster": cluster,
            "anterior": anterior,
            "autor": str(autor),
        }
    )
    dados["revision"] = nova_revisao
    _escrever_json_atomico(Path(path), dados)
    return nova_revisao


def desfazer_correcao(path: Path, *, expected_revision: str) -> str:
    """Desfaz a última correção como nova revisão (nunca reescreve história)."""
    dados = carregar_segmentos(path)
    if dados["revision"] != expected_revision:
        raise ValueError("revisão esperada divergente; recarregue a reunião")
    if not dados["historico"]:
        raise ValueError("nada a desfazer")
    ultimo = dados["historico"][-1]
    cluster = str(ultimo.get("cluster", ""))
    anterior = ultimo.get("anterior")
    if anterior is None:
        dados["mapeamento"].pop(cluster, None)
    else:
        dados["mapeamento"][cluster] = anterior
    numero = len(dados["historico"]) + 2
    nova_revisao = f"rev-{numero}"
    dados["historico"].append(
        {"revision": nova_revisao, "acao": "desfazer", "cluster": cluster}
    )
    dados["revision"] = nova_revisao
    _escrever_json_atomico(Path(path), dados)
    return nova_revisao
