"""T-13.B1 — concorrência real entre processos da fila de jobs."""
from __future__ import annotations

import json
import multiprocessing
import os
import queue
from pathlib import Path

import pytest

from fila_lock import ProcessIdentity, current_process_identity, process_matches
from fila_processamento import FilaProcessamento


def _reivindicar_em_processo(
    pasta_transcricoes: str,
    job_id: str,
    pronto,
    iniciar,
    resultados,
) -> None:
    """Alvo serializável para spawn no Windows; não compartilha lock Python."""
    fila = FilaProcessamento(pasta_transcricoes)
    pronto.set()
    if not iniciar.wait(10):
        resultados.put({"erro": "barreira expirou"})
        return
    try:
        job = fila.reivindicar(job_id)
    except RuntimeError:
        resultados.put(None)
        return
    resultados.put({"id": job.id, "pid": os.getpid()})


@pytest.fixture
def fila(tmp_path):
    pasta = tmp_path / "transcricoes"
    audio = pasta / "audio" / "reuniao.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    return FilaProcessamento(str(pasta)), str(audio)


def _bruto(fila: FilaProcessamento, job_id: str) -> dict:
    return json.loads(fila.caminho_job(job_id).read_text(encoding="utf-8"))


def test_registrar_pid_nao_reverte_processing(fila):
    instancia, audio = fila
    job_id = instancia.enfileirar(audio, None, "reuniao", {})
    instancia.reivindicar(job_id)
    antes = _bruto(instancia, job_id)

    instancia.registrar_worker(job_id, pid=os.getpid())
    depois = _bruto(instancia, job_id)

    assert depois["estado"] == "processing"
    assert depois["lease"] == antes["lease"]
    assert depois["revision"] == antes["revision"] + 1


def test_heartbeat_do_proprietario_preserva_lease_e_avanca_revisao(fila):
    instancia, audio = fila
    job_id = instancia.enfileirar(audio, None, "reuniao", {})
    instancia.reivindicar(job_id)
    antes = _bruto(instancia, job_id)

    instancia.renovar_lease(job_id)
    depois = _bruto(instancia, job_id)

    assert depois["estado"] == "processing"
    assert depois["lease"]["owner"] == antes["lease"]["owner"]
    assert depois["lease"]["nonce"] == antes["lease"]["nonce"]
    assert depois["revision"] == antes["revision"] + 1


def test_pid_reutilizado_nao_confirma_lease():
    atual = current_process_identity()
    identidade_reutilizada = ProcessIdentity(
        pid=atual.pid,
        created_at_100ns=atual.created_at_100ns + 1,
    )

    assert process_matches(identidade_reutilizada) is False


def test_dois_workers_um_claim(fila):
    instancia, audio = fila
    job_id = instancia.enfileirar(audio, None, "reuniao", {})
    contexto = multiprocessing.get_context("spawn")
    iniciar = contexto.Event()
    resultados = contexto.Queue()
    prontos = [contexto.Event(), contexto.Event()]
    processos = [
        contexto.Process(
            target=_reivindicar_em_processo,
            args=(str(instancia.pasta_transcricoes), job_id, pronto, iniciar, resultados),
        )
        for pronto in prontos
    ]
    for processo in processos:
        processo.start()
    try:
        assert all(pronto.wait(10) for pronto in prontos)
        iniciar.set()
        saidas = [resultados.get(timeout=10) for _ in processos]
    finally:
        for processo in processos:
            processo.join(timeout=10)
            if processo.is_alive():
                processo.terminate()
                processo.join(timeout=5)

    vencedor = [saida for saida in saidas if saida is not None]
    assert len(vencedor) == 1
    dados = _bruto(instancia, job_id)
    assert dados["estado"] == "processing"
    assert dados["lease"]["owner"]["pid"] == vencedor[0]["pid"]
    assert dados["lease"]["nonce"]


def test_startup_nao_reivindica_worker_vivo(fila):
    instancia, audio = fila
    job_id = instancia.enfileirar(audio, None, "reuniao", {})
    instancia.reivindicar(job_id)

    recuperadora = FilaProcessamento(str(instancia.pasta_transcricoes))
    assert recuperadora.recuperar_interrompidos() == 0
    assert recuperadora.obter(job_id).estado == "processing"


def test_json_corrompido_nao_bloqueia_fila(fila):
    instancia, audio = fila
    job_id = instancia.enfileirar(audio, None, "reuniao", {})
    instancia.reivindicar(job_id)
    dados = _bruto(instancia, job_id)
    dados["lease"] = {
        "owner": {"pid": 999_999, "created_at_100ns": 1},
        "nonce": "stale-test",
        "acquired_at_utc": "2026-09-19T12:00:00Z",
        "heartbeat_at_utc": "2026-09-19T12:00:00Z",
    }
    instancia.caminho_job(job_id).write_text(
        json.dumps(dados), encoding="utf-8"
    )

    corrompido = instancia.pasta_jobs / f"{'0' * 32}.json"
    corrompido.write_text("{", encoding="utf-8")

    assert instancia.recuperar_interrompidos() == 1
    assert instancia.obter(job_id).estado == "pending"
    assert not corrompido.exists()
    assert list(instancia.pasta_jobs.glob("*.corrupt"))
