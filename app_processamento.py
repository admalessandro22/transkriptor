# -*- coding: utf-8 -*-
"""Orquestra a fila pós-reunião sem bloquear o processo da bandeja."""
from __future__ import annotations

import datetime
import logging
import threading
import time
from pathlib import Path

from notificador import notificar
from processador_reuniao import iniciar_subprocesso


logger = logging.getLogger(__name__)


class ProcessamentoReuniaoMixin:
    """Integra captura encerrada, fila durável e um worker serial."""

    def _definir_estado_processamento(self, estado, job_id=None):
        with self._lock:
            self._estado_processamento = estado
            if job_id is not None:
                self._ultimo_job_id = job_id
        self._atualizar_tooltip()

    def _processamento_em_execucao(self):
        return getattr(self, "_estado_processamento", None) == "Processando"

    def _preparar_processamento(self):
        recuperados = self.fila.recuperar_interrompidos()
        if recuperados:
            logger.info("Jobs interrompidos recuperados: %d", recuperados)
        jobs = self.fila.listar()
        pendentes = [job for job in jobs if job.estado == "pending"]
        if pendentes:
            self._definir_estado_processamento("Em fila", pendentes[0].id)
        elif jobs:
            mapa = {"ready": "Pronta", "failed": "Falhou"}
            ultimo = max(jobs, key=lambda job: (job.atualizado_em, job.id))
            self._definir_estado_processamento(mapa.get(ultimo.estado), ultimo.id)
        self._despachar_proximo_job()

    def _despachar_proximo_job(self):
        falha_inicio = False
        with self._lock:
            worker = getattr(self, "_worker_processamento", None)
            if worker is not None and worker.poll() is None:
                return
            pendentes = self.fila.listar("pending")
            if not pendentes:
                self._worker_processamento = None
                return
            job_id = pendentes[0].id
            try:
                worker = iniciar_subprocesso(job_id)
            except Exception:
                logger.exception("Falha ao iniciar worker de pós-processamento")
                self._estado_processamento = "Falhou"
                self._ultimo_job_id = job_id
                falha_inicio = True
            else:
                self._worker_processamento = worker
                self._estado_processamento = "Processando"
                self._ultimo_job_id = job_id
        pid = getattr(worker, "pid", None)
        if pid is not None:
            try:
                self.fila.registrar_worker(job_id, pid=pid)
                logger.info(
                    "Worker de pós-processamento iniciado: job=%s pid=%s",
                    job_id,
                    pid,
                )
            except Exception:
                # A captura e o worker não podem falhar só porque a auditoria
                # de metadados ficou indisponível.
                logger.exception(
                    "Falha ao registrar início do worker: job=%s pid=%s",
                    job_id,
                    pid,
                )
        self._atualizar_tooltip()
        if falha_inicio:
            return
        threading.Thread(
            target=self._aguardar_worker,
            args=(job_id, worker),
            daemon=True,
            name="Transkriptor-PosProcessamento",
        ).start()

    def _aguardar_worker(self, job_id, worker):
        codigo = worker.wait()
        pid = getattr(worker, "pid", None)
        try:
            self.fila.registrar_saida_worker(job_id, codigo=codigo)
            logger.info(
                "Worker de pós-processamento encerrado: job=%s pid=%s codigo=%s",
                job_id,
                pid,
                codigo,
            )
        except Exception:
            logger.exception(
                "Falha ao registrar saída do worker: job=%s pid=%s codigo=%s",
                job_id,
                pid,
                codigo,
            )
        try:
            job = self.fila.obter(job_id)
            pronto = codigo == 0 and job.estado == "ready" and job.resultado
        except Exception:
            logger.exception("Falha ao consultar resultado do pós-processamento")
            job, pronto = None, False
        with self._lock:
            if self._worker_processamento is worker:
                self._worker_processamento = None
            self._estado_processamento = "Pronta" if pronto else "Falhou"
        self._atualizar_tooltip()
        if pronto:
            nome = Path(job.resultado).name
            notificar(
                "Transkriptor",
                f"Transcrição pronta: {nome}",
                visivel=True,
            )
        else:
            notificar(
                "Transkriptor",
                "Não foi possível transcrever. O áudio foi preservado.",
                visivel=True,
            )
        deve_continuar = pronto or (job is not None and job.estado != "pending")
        if deve_continuar:
            self._despachar_proximo_job()

    def _separar_audios(self, caminhos):
        principal = None
        mic = None
        for caminho in caminhos:
            nome = Path(caminho).name.lower()
            if "_mic.wav" in nome:
                mic = caminho
            elif principal is None:
                principal = caminho
        return principal, mic

    def _enfileirar_reuniao(self, transcritor, caminho_saida):
        audios = list(getattr(transcritor, "audios_preservados", None) or [])
        audio, mic = self._separar_audios(audios)
        if not audio or not caminho_saida:
            self._definir_estado_processamento("Falhou")
            self._status("Falha ao preservar o áudio da reunião.")
            return None
        fim_ms = int(time.time() * 1000)
        inicio_ms = self._inicio_transcricao_wall_ms or fim_ms
        inicio = datetime.datetime.fromtimestamp(inicio_ms / 1000).astimezone()
        fim = datetime.datetime.fromtimestamp(fim_ms / 1000).astimezone()
        metadados = {
            "origem": "reuniao_detectada",
            "inicio_iso": inicio.isoformat(),
            "fim_iso": fim.isoformat(),
            "duracao_seg": max(0.0, (fim_ms - inicio_ms) / 1000.0),
            "diarizar": bool(
                getattr(transcritor, "diarizar_ao_final", self.diarizacao_ativa)
            ),
            "identificar_voz": bool(
                getattr(transcritor, "identificar_voz", self.identificar_minha_voz)
            ),
            "criptografar": bool(
                getattr(transcritor, "criptografar", self.criptografar_transcricoes)
            ),
            "modelo": getattr(transcritor, "modelo_nome", self.modelo_whisper),
            "idioma": getattr(transcritor, "idioma", None) or "pt",
        }
        base_saida = Path(caminho_saida).stem
        job_id = self.fila.enfileirar(audio, mic, base_saida, metadados)
        self._definir_estado_processamento("Em fila", job_id)
        self._status("Reunião encerrada e colocada na fila de transcrição.")
        self._despachar_proximo_job()
        return job_id
