# -*- coding: utf-8 -*-
"""Alvos pickláveis de spawn para T-13.B3. Não importam a bandeja."""
from __future__ import annotations

import os
import time

from fila_processamento import FilaProcessamento


def vivo_sem_progresso(pasta: str, job_id: str, pronto) -> None:
    fila = FilaProcessamento(pasta)
    fila.reivindicar(job_id)
    pronto.set()
    while True:
        time.sleep(0.1)
        try:
            fila.renovar_lease(job_id)
        except Exception:
            return


def com_progresso(pasta: str, job_id: str, pare) -> None:
    fila = FilaProcessamento(pasta)
    fila.reivindicar(job_id)
    n = 0
    while not pare.is_set():
        n += 1
        fila.registrar_progresso(job_id, "transcribe", n)
        time.sleep(0.05)
    try:
        fila.renovar_lease(job_id)
    except Exception:
        return


def cooperativo(pasta: str, job_id: str, pronto) -> None:
    fila = FilaProcessamento(pasta)
    fila.reivindicar(job_id)
    pronto.set()
    while True:
        job = fila.obter(job_id)
        if getattr(job, "cancel_solicitado", False):
            fila.cancelar(job_id)
            return
        time.sleep(0.05)
        try:
            fila.renovar_lease(job_id)
        except Exception:
            return


def falha_apos_claim(pasta: str, job_id: str) -> None:
    fila = FilaProcessamento(pasta)
    fila.reivindicar(job_id)
    fila.falhar(job_id, "runtimeerror")


def sai_sem_claim(*_args) -> None:
    os._exit(1)
