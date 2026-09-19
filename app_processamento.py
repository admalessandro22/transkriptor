# -*- coding: utf-8 -*-
"""Orquestra a fila pós-reunião sem bloquear o processo da bandeja."""
from __future__ import annotations

import datetime
import logging
import subprocess
import threading
import time
from pathlib import Path

import config as _config
from notificador import notificar
from processador_reuniao import iniciar_subprocesso
from worker_liveness import avaliar_inatividade, encerrar_se_lease_valido


logger = logging.getLogger(__name__)


def _esperar_worker(worker, timeout):
    wait = getattr(worker, "wait", None)
    if wait is None:
        poll = getattr(worker, "poll", lambda: 0)
        return poll()
    try:
        return wait(timeout=timeout)
    except TypeError:
        return wait()
    except subprocess.TimeoutExpired:
        return None


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
            mapa = {"ready": "Pronta", "failed": "Falhou", "cancelled": "Cancelada"}
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
                job_observado = self.fila.registrar_worker(job_id, pid=pid)
                logger.info(
                    "Worker de pós-processamento iniciado: job=%s pid=%s",
                    job_id,
                    pid,
                )
                if job_observado.estado != "processing":
                    logger.warning(
                        "Worker iniciado antes do claim: job=%s estado=%s",
                        job_id,
                        job_observado.estado,
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
            try:
                self.fila.registrar_falha_de_spawn(job_id, "falha_inicio_worker")
            except Exception:
                logger.exception("Falha ao registrar spawn do worker: job=%s", job_id)
            threading.Thread(
                target=self._despachar_proximo_job,
                daemon=True,
                name="Transkriptor-PosProcessamento",
            ).start()
            return
        threading.Thread(
            target=self._aguardar_worker,
            args=(job_id, worker),
            daemon=True,
            name="Transkriptor-PosProcessamento",
        ).start()

    def _monotonic_ns(self):
        relogio = getattr(self, "_relogio_monotonic_ns", None)
        return relogio() if relogio is not None else time.monotonic_ns()

    def _forcar_parada_validada(self, job_id, worker):
        pid = getattr(worker, "pid", None)
        try:
            job = self.fila.obter(job_id)
        except Exception:
            return False
        terminate = getattr(worker, "terminate", None)
        if not callable(terminate):
            return False
        return encerrar_se_lease_valido(job.lease, pid, terminate)

    def _aguardar_worker(self, job_id, worker):
        poll = float(getattr(self, "_worker_poll_seg", _config.WORKER_HEARTBEAT_SEG))
        aviso = float(getattr(self, "_worker_aviso_seg", _config.WORKER_PROGRESSO_AVISO_SEG))
        falha = float(getattr(self, "_worker_falha_seg", _config.WORKER_PROGRESSO_FALHA_SEG))
        init = float(
            getattr(self, "_worker_modelo_init_seg", _config.WORKER_MODELO_INIT_SEG)
        )
        cancel_forcar = float(
            getattr(self, "_worker_cancel_forcar_seg", _config.WORKER_CANCEL_FORCAR_SEG)
        )
        max_tent = int(
            getattr(self, "_worker_max_tentativas", _config.WORKER_MAX_TENTATIVAS)
        )
        ultimo_marca = None
        ultimo_em = self._monotonic_ns()
        avisou = False
        cancel_em = None
        codigo = None
        encerrou = False
        while True:
            codigo = _esperar_worker(worker, poll)
            if codigo is not None:
                break
            agora = self._monotonic_ns()
            try:
                job = self.fila.obter(job_id)
            except Exception:
                continue
            marca = (job.stage, job.progress_units)
            if ultimo_marca is None:
                ultimo_marca = marca
            elif marca != ultimo_marca:
                ultimo_marca = marca
                ultimo_em = agora
                avisou = False
            ocioso = (agora - ultimo_em) / 1e9
            if job.cancel_solicitado:
                if cancel_em is None:
                    cancel_em = agora
                elif (agora - cancel_em) / 1e9 >= cancel_forcar:
                    self._forcar_parada_validada(job_id, worker)
                    try:
                        self.fila.finalizar_por_supervisor(
                            job_id,
                            getattr(worker, "pid", 0),
                            "cancelado",
                            estado="cancelled",
                            max_tentativas=max_tent,
                        )
                    except Exception:
                        logger.exception("Falha ao cancelar job inativo")
                    encerrou = True
                    codigo = _esperar_worker(worker, poll)
                    break
                continue
            veredito = avaliar_inatividade(job.stage, ocioso, aviso, falha, init)
            if veredito == "falha":
                self._forcar_parada_validada(job_id, worker)
                try:
                    self.fila.finalizar_por_supervisor(
                        job_id,
                        getattr(worker, "pid", 0),
                        "inatividade",
                        max_tentativas=max_tent,
                    )
                except Exception:
                    logger.exception("Falha ao encerrar job inativo")
                encerrou = True
                codigo = _esperar_worker(worker, 2)
                break
            if veredito == "aviso" and not avisou:
                logger.warning(
                    "Worker sem progresso: job=%s stage=%s", job_id, job.stage
                )
                try:
                    self.fila.registrar_aviso(job_id, "inatividade")
                except Exception:
                    logger.exception("Falha ao registrar aviso de inatividade")
                avisou = True
        pid = getattr(worker, "pid", None)
        if codigo is None:
            codigo = getattr(worker, "poll", lambda: -1)()
            if codigo is None:
                codigo = -1
        try:
            self.fila.registrar_saida_worker(job_id, codigo=int(codigo))
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
        except Exception:
            logger.exception("Falha ao consultar resultado do pós-processamento")
            job = None
        if job is not None and job.estado == "processing":
            try:
                job = self.fila.finalizar_por_supervisor(
                    job_id, pid or 0, "worker_interrompido", max_tentativas=max_tent
                )
                encerrou = True
            except Exception:
                logger.exception("Falha ao finalizar job interrompido")
        if not encerrou and job is not None and job.estado == "pending":
            try:
                job = self.fila.registrar_falha_de_spawn(job_id, "worker_antes_do_claim")
            except Exception:
                logger.exception("Falha ao registrar spawn sem claim")
        if not encerrou and job is not None and job.estado == "failed":
            try:
                job = self.fila.reabrir_se_retry(job_id, max_tentativas=max_tent)
            except Exception:
                logger.exception("Falha ao reabrir job para retry")
        pronto = bool(
            codigo == 0 and job is not None and job.estado == "ready" and job.resultado
        )
        terminal = job is None or job.estado in {"ready", "failed", "cancelled"}
        with self._lock:
            if self._worker_processamento is worker:
                self._worker_processamento = None
            if pronto:
                self._estado_processamento = "Pronta"
            elif job is not None and job.estado == "cancelled":
                self._estado_processamento = "Cancelada"
            elif job is not None and job.estado == "pending":
                self._estado_processamento = "Em fila"
            else:
                self._estado_processamento = "Falhou"
        self._atualizar_tooltip()
        if pronto:
            notificar(
                "Transkriptor",
                f"Transcrição pronta: {Path(job.resultado).name}",
                visivel=True,
            )
        elif job is not None and job.estado == "cancelled":
            notificar(
                "Transkriptor",
                "Transcrição cancelada. O áudio foi preservado.",
                visivel=True,
            )
        elif terminal:
            notificar(
                "Transkriptor",
                "Não foi possível transcrever. O áudio foi preservado.",
                visivel=True,
            )
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
        titulo = getattr(transcritor, "titulo_reuniao", None) or getattr(self, "_titulo_reuniao_atual", None)
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
        if titulo:
            metadados["titulo_reuniao"] = str(titulo)[:80]
        base_saida = Path(caminho_saida).stem
        job_id = self.fila.enfileirar(audio, mic, base_saida, metadados)
        self._definir_estado_processamento("Em fila", job_id)
        self._status("Reunião encerrada e colocada na fila de transcrição.")
        self._despachar_proximo_job()
        return job_id
