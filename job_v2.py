# -*- coding: utf-8 -*-
"""Contrato do job v2: sessão, refs de eventos e preferências (T-13.D5).

Extraído de `fila_processamento.py` para manter o limite de 500 linhas.
"""
from __future__ import annotations

from pathlib import Path


CHAVES_METADADOS = {
    "origem",
    "inicio_iso",
    "fim_iso",
    "duracao_seg",
    "diarizar",
    "identificar_voz",
    "criptografar",
    "modelo",
    "idioma",
    "lacuna_estimada_seg",
    "titulo_reuniao",
}


def metadados_seguros(metadados: dict | None) -> dict:
    seguros = {}
    for chave, valor in dict(metadados or {}).items():
        if chave not in CHAVES_METADADOS:
            continue
        if isinstance(valor, (bool, int, float)) or valor is None:
            seguros[chave] = valor
        elif isinstance(valor, str) and len(valor) <= 80:
            seguros[chave] = valor
    return seguros


def refs_eventos_seguras(refs, raiz: Path) -> list[dict]:
    """Valida refs de eventos: estrutura + artefato íntegro dentro da raiz."""
    from artefatos import ArtifactRef, referencia_integra

    seguras: list[dict] = []
    for ref in refs or ():
        if not isinstance(ref, dict):
            raise ValueError("ref de evento inválida")
        try:
            artefato = ArtifactRef(
                relative_path=str(ref["relative_path"]),
                format=str(ref["format"]),
                schema_version=int(ref["schema_version"]),
                sha256=str(ref["sha256"]),
                size_bytes=int(ref["size_bytes"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"ref de evento inválida: {exc}") from exc
        if artefato.format != "meet-events-jsonl-enc" or artefato.schema_version != 1:
            raise ValueError("ref de evento com formato/versão desconhecidos")
        if not referencia_integra(artefato, Path(raiz)):
            raise ValueError("ref de evento sem artefato íntegro")
        seguras.append(
            {
                "relative_path": artefato.relative_path,
                "format": artefato.format,
                "schema_version": artefato.schema_version,
                "sha256": artefato.sha256,
                "size_bytes": artefato.size_bytes,
            }
        )
    return seguras


def sessao_segura(sessao) -> dict | None:
    if sessao is None:
        return None
    if not isinstance(sessao, dict):
        raise ValueError("sessão de job inválida")
    for campo in ("session_id", "meeting_key", "consented_at_utc", "policy_id"):
        valor = sessao.get(campo)
        if not isinstance(valor, str) or not valor:
            raise ValueError(f"sessão de job sem {campo}")
    saida = {k: sessao[k] for k in ("session_id", "meeting_key", "consented_at_utc", "policy_id")}
    for opcional in ("first_frame_monotonic_ns", "offset_ms", "relogio_incerto"):
        if opcional in sessao:
            saida[opcional] = sessao[opcional]
    return saida


def preferencias_seguras(preferencias) -> dict | None:
    if preferencias is None:
        return None
    if not isinstance(preferencias, dict):
        raise ValueError("preferências de job inválidas")
    saida: dict = {}
    rotulo = preferencias.get("rotulo_usuario")
    if isinstance(rotulo, str) and rotulo and len(rotulo) <= 80:
        saida["rotulo_usuario"] = rotulo
    if "usar_vozes_conhecidas" in preferencias:
        saida["usar_vozes_conhecidas"] = bool(preferencias["usar_vozes_conhecidas"])
    return saida


def validar_para_salvar(dados: dict) -> None:
    if dados.get("sessao") is not None and not isinstance(dados.get("sessao"), dict):
        raise ValueError("sessão de job inválida")
    if not isinstance(dados.get("eventos_refs", []), list):
        raise ValueError("refs de eventos inválidas")


def normalizar_leitura(dados: dict) -> dict:
    dados.setdefault("sessao", None)
    dados.setdefault("eventos_refs", [])
    dados.setdefault("preferencias", None)
    if dados.get("sessao") is not None:
        dados["sessao"] = sessao_segura(dados["sessao"])
    if dados.get("preferencias") is not None:
        dados["preferencias"] = preferencias_seguras(dados["preferencias"])
    for ref in dados.get("eventos_refs") or ():
        if not isinstance(ref, dict) or not ref.get("relative_path"):
            raise ValueError("ref de evento inválida")
    return dados


def anexar_v2(dados: dict, *, sessao, eventos_refs, preferencias, raiz: Path) -> None:
    dados["sessao"] = sessao_segura(sessao)
    dados["eventos_refs"] = refs_eventos_seguras(eventos_refs, raiz)
    dados["preferencias"] = preferencias_seguras(preferencias)


def ler_v2(dados: dict) -> tuple:
    refs = tuple(dict(r) for r in (dados.get("eventos_refs") or ()))
    prefs = dados.get("preferencias")
    return (
        dict(dados["sessao"]) if dados.get("sessao") is not None else None,
        refs,
        dict(prefs) if prefs is not None else None,
    )
