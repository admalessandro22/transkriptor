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
        resultado = retranscritor.retranscrever(
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
            on_status=_on_status,
        )
        if fila.obter(job_id).cancel_solicitado:
            raise JobCancelado("cancelado")
        from resultado_reuniao import criar_manifesto_inicial, salvar_manifesto

        caminho_resultado = Path(resultado)
        fontes_audio = [Path(job.audio)]
        if job.mic:
            fontes_audio.append(Path(job.mic))
        manifesto = criar_manifesto_inicial(
            meeting_id=job.id,
            resultado=caminho_resultado,
            fontes_audio=fontes_audio,
            raiz=fila.pasta_transcricoes,
        )
        caminho_manifesto = caminho_resultado.with_suffix(".resultado.json")
        salvar_manifesto(caminho_manifesto, manifesto)
        fila.registrar_progresso(job_id, ETAPA_FINAL, unidades + 1)
        if fila.obter(job_id).cancel_solicitado:
            raise JobCancelado("cancelado")
        fila.concluir(job_id, resultado, str(caminho_manifesto))
        return Path(resultado)
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
