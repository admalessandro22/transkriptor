#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avalia qualidade de reunião: WER/DER, precisão nominal e cobertura (T-13.G3).

Referências versionadas por hash (nunca gravações pessoais no repo);
conjuntos de calibração e teste separados. Roster sozinho nunca nomeia.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(texto: str) -> list[str]:
    return _TOKEN_RE.findall(str(texto or "").lower())


def wer(referencia: str, hipotese: str) -> float:
    """Taxa de erro de palavra (S+D+I)/N sobre tokens normalizados."""
    ref, hyp = _tokens(referencia), _tokens(hipotese)
    if not ref:
        return 0.0 if not hyp else 1.0
    anterior = list(range(len(hyp) + 1))
    for i, tramo in enumerate(ref, 1):
        atual = [i]
        for j, tramo_h in enumerate(hyp, 1):
            atual.append(
                min(
                    anterior[j] + 1,
                    atual[j - 1] + 1,
                    anterior[j - 1] + (tramo != tramo_h),
                )
            )
        anterior = atual
    return anterior[-1] / len(ref)


def _sobrepoe(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def der(
    referencia: list, hipotese: list, *, politica_sobreposicao: str = "perdoar"
) -> float:
    """Taxa de erro de diarização temporal (falso alarme + perda + confusão).

    `politica_sobreposicao`: "perdoar" ignora trechos sobrepostos na
    referência; "rigorosa" conta sobreposição como erro quando há um só
    falante hipotético. Política sempre declarada no relatório.
    """
    if politica_sobreposicao not in ("perdoar", "rigorosa"):
        raise ValueError("política de sobreposição desconhecida")
    total_fala = sum(max(0.0, float(s.get("fim", 0)) - float(s.get("inicio", 0))) for s in referencia)
    if total_fala <= 0:
        return 0.0
    if politica_sobreposicao == "perdoar":
        segmentos = [s for s in referencia if not s.get("overlap")]
        base = segmentos or list(referencia)
    else:
        base = list(referencia)
    erro = 0.0
    for seg in base:
        ini, fim = float(seg["inicio"]), float(seg["fim"])
        dur = max(0.0, fim - ini)
        coberto = sum(
            _sobrepoe(ini, fim, float(h.get("inicio", 0)), float(h.get("fim", 0)))
            for h in hipotese
        )
        certo = sum(
            _sobrepoe(ini, fim, float(h.get("inicio", 0)), float(h.get("fim", 0)))
            for h in hipotese
            if h.get("falante") == seg.get("falante")
        )
        erro += (dur - min(dur, coberto)) + (min(dur, coberto) - certo)
    for h in hipotese:
        dur_h = max(0.0, float(h.get("fim", 0)) - float(h.get("inicio", 0)))
        coberto_h = sum(
            _sobrepoe(float(h.get("inicio", 0)), float(h.get("fim", 0)),
                      float(s.get("inicio", 0)), float(s.get("fim", 0)))
            for s in base
        )
        erro += max(0.0, dur_h - coberto_h)
    return min(1.0, erro / total_fala)


def metricas_nominais(pares) -> dict:
    """Precisão seletiva, coberturas e abstinências (roster não nomeia)."""
    nomeados = 0
    corretos = 0
    elegiveis = 0
    abstencoes = 0
    for atrib, verdade in pares:
        status = str(atrib.get("status", "unknown"))
        nome = atrib.get("nome")
        e_roster = bool(atrib.get("roster_sem_fala"))
        if status in ("unknown", "conflict") or not nome:
            abstencoes += 1
        else:
            nomeados += 1
            if not e_roster and verdade is not None and nome == verdade:
                corretos += 1
        if verdade is not None:
            elegiveis += 1
    total = len(list(pares))
    return {
        "total": total,
        "nomeados": nomeados,
        "corretos": corretos,
        "precisao_seletiva": (corretos / nomeados) if nomeados else 0.0,
        "cobertura_elegivel": (corretos / elegiveis) if elegiveis else 0.0,
        "cobertura_total": (corretos / total) if total else 0.0,
        "abstencoes": abstencoes,
    }


def intervalo_wilson(acertos: int, total: int) -> tuple[float, float]:
    """IC95% de Wilson para proporções (G3 publica com intervalo)."""
    if total <= 0:
        return (0.0, 0.0)
    z = 1.96
    p = acertos / total
    denominador = 1 + z * z / total
    centro = p + z * z / (2 * total)
    margem = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (max(0.0, (centro - margem) / denominador), min(1.0, (centro + margem) / denominador))


def hash_referencia(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--referencia", required=True, help="JSONL de referência")
    parser.add_argument("--hipotese", required=True, help="JSONL do sistema")
    parser.add_argument("--politica-sobreposicao", default="perdoar",
                        choices=["perdoar", "rigorosa"])
    args = parser.parse_args(argv)
    ref_path, hyp_path = Path(args.referencia), Path(args.hipotese)
    refs = [json.loads(l) for l in ref_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    hyps = [json.loads(l) for l in hyp_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    por_id = {h.get("segment_id"): h for h in hyps if isinstance(h, dict)}
    pares, wers, segs_ref, segs_hyp = [], [], [], []
    for r in refs:
        if not isinstance(r, dict):
            continue
        h = por_id.get(r.get("segment_id"), {})
        texto_r, texto_h = str(r.get("text", "")), str(h.get("text", ""))
        wers.append(wer(texto_r, texto_h))
        segs_ref.append({"inicio": r.get("start_ms", 0) / 1000.0, "fim": r.get("end_ms", 0) / 1000.0,
                         "falante": r.get("speaker"), "overlap": r.get("overlap", False)})
        segs_hyp.append({"inicio": h.get("start_ms", 0) / 1000.0, "fim": h.get("end_ms", 0) / 1000.0,
                         "falante": h.get("speaker"), "overlap": h.get("overlap", False)})
        pares.append((
            {"nome": h.get("speaker"), "status": h.get("status", "unknown"),
             "roster_sem_fala": bool(h.get("roster_sem_fala", False))},
            r.get("speaker"),
        ))
    nominal = metricas_nominais(pares)
    lo, hi = intervalo_wilson(nominal["corretos"], nominal["nomeados"])
    relatorio = {
        "wer_medio": sum(wers) / len(wers) if wers else 0.0,
        "der": der(segs_ref, segs_hyp, politica_sobreposicao=args.politica_sobreposicao),
        "politica_sobreposicao": args.politica_sobreposicao,
        "nominal": nominal,
        "precisao_ic95": [lo, hi],
        "ref_sha256": hash_referencia(ref_path),
        "hipotese_sha256": hash_referencia(hyp_path),
        "n_segmentos": len(refs),
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
