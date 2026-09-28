# -*- coding: utf-8 -*-
"""Reparo confinado de diarização de uma reunião já processada."""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from pathlib import Path


def _diarizar_job(job, dados: dict) -> list[tuple[str, float, float, str]]:
    from audio_reader import AudioSource
    from audio_trechos import extrair_trechos, selecionar_trechos_por_fonte
    from config import ROTULO_USUARIO
    from diarizacao_final import rodar_diarizacao
    from processador_reuniao import carregar_eventos_job
    from transcricao_core import Transcritor

    raiz = Path(job.resultado).resolve().parent
    intervalos = [
        (seg["start_ms"] / 1000.0, seg["end_ms"] / 1000.0, seg["text"])
        for seg in dados["segmentos"]
    ]
    eventos, avisos = carregar_eventos_job(job, raiz)
    if avisos:
        raise ValueError("eventos da reunião indisponíveis para o reparo")
    trechos_lb = extrair_trechos(Path(job.audio), AudioSource.LOOPBACK, intervalos)
    trechos_mic = (
        extrair_trechos(Path(job.mic), AudioSource.MICROPHONE, intervalos)
        if job.mic else None
    )
    trechos_por_origem = selecionar_trechos_por_fonte(
        [seg["audio_source"] for seg in dados["segmentos"]], trechos_lb, trechos_mic,
    )
    preferencias = job.preferencias or {}
    transcritor = Transcritor(
        pasta_saida=str(raiz), diarizar_ao_final=True, capturar_mic=False,
        identificar_voz=bool(job.metadados.get("identificar_voz", False)),
        rotulo_usuario=preferencias.get("rotulo_usuario") or ROTULO_USUARIO,
        eventos_meet=eventos,
        usar_vozes_conhecidas=bool(preferencias.get("usar_vozes_conhecidas", True)),
        criptografar=Path(job.audio).suffix.lower() == ".tks",
        on_status=lambda msg: print(msg, flush=True)
        if re.fullmatch(r"\d+/\d+ segmentos\.\.\.", str(msg)) else None,
    )
    transcritor._segmentos = intervalos
    transcritor._preservar_audios = lambda *_caminhos: []
    return rodar_diarizacao(
        transcritor, None, None, trechos_audio=trechos_por_origem,
        trechos_mic=trechos_mic, trechos_loopback=trechos_lb,
        materializar=False,
    ) or []


def reparar(raiz: Path, meeting_id: str, *, aplicar: bool = False,
            refazer_origens: bool = False, diarizar_fn=None) -> dict:
    from artefatos import criar_referencia, referencia_integra
    from audio_fontes import SegmentoSTT
    from audio_reader import AudioSource
    from fila_processamento import FilaProcessamento
    from indice_transcricoes import atualizar_indice
    from politica_privacidade import ProtectionMode
    from resultado_edicao import exportar_txt
    from resultado_pipeline import criar_segmentos
    from resultado_reuniao import (
        StageState, salvar_manifesto, validar_manifesto, validar_manifesto_para_job,
    )
    from resultado_storage import FORMATO_CIFRADO, ResultadoStorage

    raiz = Path(raiz).resolve(strict=True)
    fila = FilaProcessamento(str(raiz))
    job = fila.obter(meeting_id)
    if job.estado != "ready":
        raise ValueError("job não está pronto")
    fontes = [Path(job.audio)]
    if job.mic:
        fontes.append(Path(job.mic))
    try:
        validar_manifesto_para_job(
            resultado=Path(job.resultado),
            manifesto=Path(job.manifesto_resultado),
            fontes_audio=fontes, raiz=raiz,
        )
    except (OSError, ValueError) as exc:
        raise ValueError("manifesto ou fontes inválidos") from exc
    from resultado_reuniao import carregar_manifesto

    manifesto = carregar_manifesto(Path(job.manifesto_resultado))
    modo = (ProtectionMode.PROTECTED if manifesto.segments_ref.format == FORMATO_CIFRADO
            else ProtectionMode.COMPATIBLE)
    storage = ResultadoStorage(raiz, modo)
    dados = storage.load(manifesto.segments_ref)
    if refazer_origens:
        if manifesto.stage_status.get("diarizacao") is not StageState.COMPLETE:
            raise ValueError("refazer origens exige diarização previamente completa")
    elif (manifesto.stage_status.get("diarizacao") is not StageState.PARTIAL
          or "segment_alignment_failed" not in manifesto.warnings):
        raise ValueError("reunião não tem falha de alinhamento reparável")
    if dados.get("mapeamento") or dados.get("historico"):
        raise ValueError("resultado com revisão manual exige tratamento específico")
    if "diarizacao_falhou" in manifesto.warnings:
        raise ValueError("diarização original falhou; reparo de alinhamento insuficiente")
    if not aplicar:
        return {
            "estado": "inspecao", "meeting_id": meeting_id,
            "segmentos": len(dados["segmentos"]), "revision": dados["revision"],
        }
    diarizados = (diarizar_fn or _diarizar_job)(job, dados)
    originais = dados["segmentos"]
    if not diarizados or len(diarizados) != len(originais):
        raise ValueError("alinhamento da diarização ainda incompleto")
    fundidos = [
        SegmentoSTT(
            str(seg["segment_id"]), int(seg["start_ms"]), int(seg["end_ms"]),
            AudioSource(seg["audio_source"]), str(seg["text"]), bool(seg.get("overlap")),
        )
        for seg in originais
    ]
    atribuicoes = {seg["segment_id"]: seg.get("assignment") for seg in originais}
    novos, avisos = criar_segmentos(fundidos, diarizados, atribuicoes)
    if avisos or len(novos) != len(originais):
        raise ValueError("alinhamento da diarização ainda incompleto")
    if any(
        (novo.segment_id, novo.start_ms, novo.end_ms, novo.text, novo.audio_source)
        != (antigo["segment_id"], antigo["start_ms"], antigo["end_ms"],
            antigo["text"], antigo["audio_source"])
        for novo, antigo in zip(novos, originais)
    ):
        raise ValueError("reparo alteraria falas ou horários")
    novo_payload = dict(dados)
    novo_payload["segmentos"] = [
        {**antigo, "speaker_cluster_id": novo.speaker_cluster_id}
        for antigo, novo in zip(originais, novos)
    ]
    revisao = ("rev-origens-" if refazer_origens else "rev-reparo-") + hashlib.sha256(
        Path(job.manifesto_resultado).read_bytes()
    ).hexdigest()[:12]
    novo_payload["revision"] = revisao
    texto = exportar_txt(novo_payload["segmentos"], novo_payload["mapeamento"])

    with storage._lock(meeting_id):
        caminho_manifesto, atual = storage._manifesto_sem_lock(meeting_id)
        if (Path(job.manifesto_resultado).resolve() != caminho_manifesto.resolve()
                or atual.segments_ref != manifesto.segments_ref
                or storage.load(atual.segments_ref)["revision"] != dados["revision"]):
            raise ValueError("reunião alterada durante o reparo")
        refs_saida = list(atual.exports)
        if len(refs_saida) != 1 or not referencia_integra(refs_saida[0], raiz):
            raise ValueError("exportação inválida")
        ref_saida = refs_saida[0]
        caminho_saida = raiz / ref_saida.relative_path
        caminho_json = raiz / atual.segments_ref.relative_path
        storage._criar_journal(meeting_id, caminho_manifesto, caminho_json, caminho_saida)
        try:
            novo_ref = storage.save(meeting_id, novo_payload)
            if modo == ProtectionMode.PROTECTED:
                from crypto_storage import salvar_transcricao

                salvar_transcricao(str(caminho_saida), texto)
            else:
                from retranscritor import _escrever_texto_atomico

                _escrever_texto_atomico(caminho_saida, texto)
            nova_saida = criar_referencia(
                caminho_saida, raiz, format=ref_saida.format,
                schema_version=ref_saida.schema_version,
            )
            novo_manifesto = replace(
                atual, segments_ref=novo_ref, exports=(nova_saida,),
                stage_status={**atual.stage_status, "diarizacao": StageState.COMPLETE},
                warnings=tuple(w for w in atual.warnings if w != "segment_alignment_failed"),
            )
            salvar_manifesto(caminho_manifesto, novo_manifesto)
            if not validar_manifesto(caminho_manifesto, raiz):
                raise ValueError("manifesto reparado inválido")
            validar_manifesto_para_job(
                resultado=caminho_saida, manifesto=caminho_manifesto,
                fontes_audio=fontes, raiz=raiz,
            )
            atualizar_indice(raiz / "indice.json", novo_manifesto)
            storage._limpar_journal(meeting_id)
        except Exception:
            storage._recuperar_journal(meeting_id)
            raise
    return {
        "estado": "reparado", "meeting_id": meeting_id,
        "segmentos": len(novos), "revision": revisao,
    }


def main(argv=None) -> int:
    import argparse
    import json

    from config import PASTA_TRANSCRICOES

    parser = argparse.ArgumentParser(description="Inspeciona ou repara uma reunião por ID")
    parser.add_argument("--meeting-id", required=True)
    parser.add_argument("--raiz", type=Path, default=Path(PASTA_TRANSCRICOES))
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--refazer-origens", action="store_true",
                        help="recalcula rótulos de reunião completa usando a fonte de cada fala")
    args = parser.parse_args(argv)
    try:
        resultado = reparar(args.raiz, args.meeting_id, aplicar=args.aplicar,
                            refazer_origens=args.refazer_origens)
    except Exception as exc:
        print(json.dumps({
            "estado": "recusado", "tipo": type(exc).__name__,
            "motivo": str(exc)[:200],
        }, ensure_ascii=False))
        return 1
    print(json.dumps(resultado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
