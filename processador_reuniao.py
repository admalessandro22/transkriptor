# -*- coding: utf-8 -*-
"""Worker pós-reunião executado fora do processo da bandeja."""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import config as _config
from fila_processamento import FilaProcessamento, fila_padrao
from worker_liveness import ETAPA_FINAL, ETAPA_MODELO, ETAPA_TRANSCRICAO

logger = logging.getLogger(__name__)


class JobCancelado(RuntimeError):
    """Cancelamento cooperativo observado pelo worker."""


def flags_subprocesso_windows() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
        getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    )


def carregar_eventos_job(job, raiz_transcricoes) -> tuple[list[dict], list[str]]:
    """Carrega eventos das refs do job v2 com hash validado (T-13.D5).

    Retorna (eventos, avisos). Ref inválida/adulterada é recusada sem
    fabricar nomes; o job segue sem eventos (identificação indisponível).
    """
    import json as _json

    from artefatos import ArtifactRef, referencia_integra

    eventos: list[dict] = []
    avisos: list[str] = []
    for ref_dict in job.eventos_refs or ():
        try:
            ref = ArtifactRef(
                relative_path=str(ref_dict["relative_path"]),
                format=str(ref_dict["format"]),
                schema_version=int(ref_dict["schema_version"]),
                sha256=str(ref_dict["sha256"]),
                size_bytes=int(ref_dict["size_bytes"]),
            )
        except (KeyError, TypeError, ValueError):
            avisos.append("evento_ref_invalida_recusada")
            continue
        try:
            if not referencia_integra(ref, Path(raiz_transcricoes)):
                raise ValueError("hash divergente")
            from crypto_storage import ler_bytes_arquivo

            caminho = (Path(raiz_transcricoes) / ref.relative_path).resolve()
            plano = ler_bytes_arquivo(str(caminho))
        except Exception:  # noqa: BLE001 — hash/formato/cifra: recusa sem nomes
            avisos.append("evento_hash_invalido_recusado")
            continue
        try:
            for linha in plano.decode("utf-8").splitlines():
                evento = _json.loads(linha)
                if isinstance(evento, dict):
                    eventos.append(evento)
        except (ValueError, UnicodeDecodeError):
            avisos.append("evento_ref_invalida_recusada")
            return [], avisos
    return eventos, avisos


def iniciar_subprocesso(job_id: str):
    """Inicia um worker sem console e abaixo da prioridade da bandeja."""
    return subprocess.Popen(
        [sys.executable, "-m", "processador_reuniao", "--job", job_id],
        cwd=str(Path(__file__).resolve().parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags_subprocesso_windows(),
        close_fds=True,
    )


def processar_job(
    job_id: str,
    *,
    modelo_whisper=None,
    fila: FilaProcessamento | None = None,
) -> Path:
    fila = fila or fila_padrao()
    job = fila.obter(job_id)
    if job.estado == "pending":
        job = fila.reivindicar(job_id)
    elif job.estado == "ready" and job.resultado:
        return Path(job.resultado)
    elif job.estado != "processing":
        raise RuntimeError("job não pode ser processado neste estado")
    else:
        job = fila.renovar_lease(job_id)

    parar_heartbeat = threading.Event()
    unidades = 0

    def _heartbeat():
        intervalo = float(_config.WORKER_HEARTBEAT_SEG)
        while not parar_heartbeat.wait(intervalo):
            try:
                atual = fila.renovar_lease(job_id)
            except Exception:
                return
            if atual.cancel_solicitado:
                return

    def _on_status(msg):
        nonlocal unidades
        unidades += 1
        texto = str(msg or "")
        if texto.startswith("transcribe:"):
            etapa = ETAPA_TRANSCRICAO
        elif unidades == 1:
            etapa = ETAPA_MODELO
        else:
            etapa = ETAPA_TRANSCRICAO
        fila.registrar_progresso(job_id, etapa, unidades)
        if fila.obter(job_id).cancel_solicitado:
            raise JobCancelado("cancelado")

    pulso = threading.Thread(
        target=_heartbeat, daemon=True, name="Transkriptor-WorkerHeartbeat"
    )
    try:
        import retranscritor

        # O worker real reafirma a própria identidade depois do claim. A bandeja
        # pode ter registrado o PID do subprocesso antes de ele ganhar o lease.
        fila.registrar_worker(job_id, pid=os.getpid())
        fila.registrar_progresso(job_id, ETAPA_MODELO, 0)
        pulso.start()
        if fila.obter(job_id).cancel_solicitado:
            raise JobCancelado("cancelado")
        metadados = dict(job.metadados)
        fila.registrar_progresso(job_id, ETAPA_TRANSCRICAO, max(unidades, 1))
        eventos_meet, avisos_eventos = carregar_eventos_job(job, fila.pasta_transcricoes)
        for aviso in avisos_eventos:
            try:
                fila.registrar_aviso(job_id, aviso)
            except Exception:
                logger.error("Falha ao registrar aviso de eventos")
        preferencias = dict(job.preferencias or {})
        processamento = retranscritor.retranscrever_resultado(
            job.audio,
            caminho_mic=job.mic,
            pasta_saida=str(fila.pasta_transcricoes),
            nome_base_saida=job.base_saida,
            modelo_whisper=modelo_whisper,
            modelo_nome=metadados.get("modelo"),
            idioma=str(metadados.get("idioma") or "pt"),
            diarizar=bool(metadados.get("diarizar", True)),
            gerar_copia_tkpt=bool(metadados.get("criptografar", False)),
            metadados=metadados,
            identificar_voz=bool(metadados.get("identificar_voz", False)),
            usar_vozes_conhecidas=bool(preferencias.get("usar_vozes_conhecidas", True)),
            rotulo_usuario=preferencias.get("rotulo_usuario"),
            eventos_meet=eventos_meet,
            on_status=_on_status,
        )
        if fila.obter(job_id).cancel_solicitado:
            raise JobCancelado("cancelado")
        from resultado_reuniao import (
            carregar_segmentos, criar_manifesto_estruturado, exportar_txt,
            salvar_manifesto, salvar_segmentos, validar_manifesto,
        )

        caminho_resultado = Path(processamento.txt_path)
        caminho_segmentos = fila.pasta_transcricoes / "resultados" / f"{job.id}.json"
        if caminho_resultado.exists() or caminho_segmentos.exists():
            raise FileExistsError("resultado existente; revisão manual preservada")
        salvar_segmentos(caminho_segmentos, processamento.segmentos, {})
        dados_segmentos = carregar_segmentos(caminho_segmentos)
        texto_txt = exportar_txt(dados_segmentos["segmentos"], dados_segmentos["mapeamento"])
        retranscritor._escrever_texto_atomico(caminho_resultado, texto_txt)
        if processamento.gerar_copia_tkpt:
            from crypto_storage import salvar_transcricao

            salvar_transcricao(str(caminho_resultado.with_suffix(".tkpt")), texto_txt)
        fontes_audio = [Path(job.audio)]
        if job.mic:
            fontes_audio.append(Path(job.mic))
        manifesto = criar_manifesto_estruturado(
            meeting_id=job.id,
            segmentos=caminho_segmentos,
            resultado=caminho_resultado,
            fontes_audio=fontes_audio,
            raiz=fila.pasta_transcricoes,
            warnings=processamento.warnings,
            diarizacao_solicitada=bool(metadados.get("diarizar", True)),
        )
        caminho_manifesto = caminho_resultado.with_suffix(".resultado.json")
        salvar_manifesto(caminho_manifesto, manifesto)
        if not validar_manifesto(caminho_manifesto, fila.pasta_transcricoes):
            raise ValueError("manifesto estruturado inválido")
        fila.registrar_progresso(job_id, ETAPA_FINAL, unidades + 1)
        if fila.obter(job_id).cancel_solicitado:
            raise JobCancelado("cancelado")
        fila.concluir(job_id, str(caminho_resultado), str(caminho_manifesto))
        return caminho_resultado
    except JobCancelado:
        try:
            fila.cancelar(job_id)
        except Exception:
            logger.error("Falha ao marcar job como cancelled")
        logger.info("Pós-processamento cancelado")
        return Path(job.audio)
    except Exception as exc:
        codigo = type(exc).__name__.lower()
        try:
            fila.falhar(job_id, codigo)
        except Exception:
            logger.error("Falha ao marcar job como failed")
        logger.error("Pós-processamento falhou (%s)", type(exc).__name__)
        raise
    finally:
        parar_heartbeat.set()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Processa uma reunião enfileirada")
    parser.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    try:
        processar_job(args.job)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
