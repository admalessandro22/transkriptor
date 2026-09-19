# -*- coding: utf-8 -*-
"""T-13.B3 / FR-13.B3 — heartbeat, timeout, retry e cancelamento do worker."""
from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

import app_processamento
import config
from fila_processamento import FilaProcessamento
from tests import alvos_worker_liveness as alvos


def _wav(pasta: Path, nome: str = "reuniao.wav") -> str:
    audio_dir = pasta / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio = audio_dir / nome
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    return str(audio)


def _bruto(fila: FilaProcessamento, job_id: str) -> dict:
    return json.loads(fila.caminho_job(job_id).read_text(encoding="utf-8"))


class _ProcWorker:
    """Adapta multiprocessing.Process à API Popen usada pelo supervisor."""

    def __init__(self, proc, terminados: list[int]):
        self._proc = proc
        self.pid = proc.pid
        self._terminados = terminados

    def poll(self):
        if self._proc.is_alive():
            return None
        return self._proc.exitcode

    def wait(self, timeout=None):
        self._proc.join(timeout)
        if self._proc.is_alive():
            raise subprocess.TimeoutExpired(["worker"], timeout or 0)
        return int(self._proc.exitcode or 0)

    def terminate(self):
        self._terminados.append(self.pid)
        if self._proc.is_alive():
            self._proc.terminate()


class _WorkerMorto:
    pid = 4242

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        return None


def _app(fila: FilaProcessamento, relogio):
    app = app_processamento.ProcessamentoReuniaoMixin.__new__(
        app_processamento.ProcessamentoReuniaoMixin
    )
    app._lock = threading.Lock()
    app._worker_processamento = None
    app._estado_processamento = None
    app._ultimo_job_id = None
    app.fila = fila
    app._atualizar_tooltip = lambda: None
    app._relogio_monotonic_ns = relogio.monotonic_ns
    app._worker_poll_seg = 0.05
    app._worker_aviso_seg = 120
    app._worker_falha_seg = 600
    app._worker_modelo_init_seg = 600
    app._worker_cancel_forcar_seg = 1
    return app


def _avancar_relogio(relogio, ms: int, passo_ms: int = 20_000) -> None:
    restante = ms
    while restante > 0:
        salto = min(passo_ms, restante)
        relogio.avancar_ms(salto)
        restante -= salto
        time.sleep(0.03)


def _esperar_waiter(waiter: threading.Thread, timeout: float = 4) -> None:
    waiter.join(timeout=timeout)
    assert waiter.is_alive() is False


@pytest.fixture
def fila_liveness(tmp_path):
    pasta = tmp_path / "transcricoes"
    pasta.mkdir()
    audio = _wav(pasta)
    fila = FilaProcessamento(str(pasta))
    return fila, audio, pasta


@pytest.fixture
def ctx_spawn():
    ctx = multiprocessing.get_context("spawn")
    processos: list = []
    waiters: list[threading.Thread] = []
    yield ctx, processos, waiters
    for waiter in waiters:
        waiter.join(timeout=2)
    limite = time.time() + 3
    while time.time() < limite:
        vivos = [
            t
            for t in threading.enumerate()
            if t.name.startswith("Transkriptor-Pos") and t.is_alive()
        ]
        if not vivos:
            break
        time.sleep(0.05)
    for proc in processos:
        if proc.is_alive():
            proc.terminate()
        proc.join(timeout=2)


def test_constantes_de_liveness_vivem_em_config():
    assert config.WORKER_HEARTBEAT_SEG == 5
    assert config.WORKER_PROGRESSO_AVISO_SEG == 120
    assert config.WORKER_PROGRESSO_FALHA_SEG == 600
    assert config.WORKER_MODELO_INIT_SEG == 600
    assert config.WORKER_MAX_TENTATIVAS == 2
    assert config.WORKER_HEARTBEAT_SEG != config.WORKER_PROGRESSO_FALHA_SEG


def test_worker_vivo_sem_progresso_libera_fila(
    fila_liveness, ctx_spawn, monkeypatch, relogio_controlado
):
    fila, audio, _pasta = fila_liveness
    ctx, processos, waiters = ctx_spawn
    job1 = fila.enfileirar(audio, None, "job-um", {})
    job2 = fila.enfileirar(audio, None, "job-dois", {})
    terminados: list[int] = []
    pronto = ctx.Event()
    hung = ctx.Process(
        target=alvos.vivo_sem_progresso,
        args=(str(fila.pasta_transcricoes), job1, pronto),
    )
    hung.start()
    processos.append(hung)
    assert pronto.wait(10)
    worker = _ProcWorker(hung, terminados)
    app = _app(fila, relogio_controlado)
    app._worker_max_tentativas = 1
    despachados: list[str] = []

    def iniciar(job_id):
        despachados.append(job_id)
        if job_id == job2:
            return _WorkerMorto()
        pytest.fail("job inativo não deve ser redispachado após falha terminal")

    monkeypatch.setattr(app_processamento, "iniciar_subprocesso", iniciar)
    monkeypatch.setattr(app_processamento, "notificar", lambda *a, **k: None)
    app._worker_processamento = worker

    waiter = threading.Thread(
        target=app._aguardar_worker, args=(job1, worker), daemon=True
    )
    waiters.append(waiter)
    waiter.start()
    _avancar_relogio(relogio_controlado, 600_000)
    _esperar_waiter(waiter)
    app._despachar_proximo_job = lambda: None

    job = fila.obter(job1)
    bruto = _bruto(fila, job1)
    assert job.estado == "failed"
    assert bruto.get("erro_seguro")
    assert Path(audio).is_file()
    assert hung.pid in terminados
    assert all(pid == hung.pid for pid in terminados)
    assert job2 in despachados
    assert os.getpid() not in terminados


def test_progresso_real_renova_deadline(
    fila_liveness, ctx_spawn, monkeypatch, relogio_controlado
):
    fila, audio, _pasta = fila_liveness
    ctx, processos, waiters = ctx_spawn
    job_id = fila.enfileirar(audio, None, "job-lento", {})
    terminados: list[int] = []
    pare = ctx.Event()
    vivo = ctx.Process(
        target=alvos.com_progresso,
        args=(str(fila.pasta_transcricoes), job_id, pare),
    )
    vivo.start()
    processos.append(vivo)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            if _bruto(fila, job_id).get("progress_units", 0) >= 2:
                break
        except Exception:
            pass
        time.sleep(0.05)
    else:
        pytest.fail("worker de progresso não persistiu unidades")

    worker = _ProcWorker(vivo, terminados)
    app = _app(fila, relogio_controlado)
    monkeypatch.setattr(app_processamento, "notificar", lambda *a, **k: None)
    app._despachar_proximo_job = lambda: None
    app._worker_processamento = worker

    waiter = threading.Thread(
        target=app._aguardar_worker, args=(job_id, worker), daemon=True
    )
    waiters.append(waiter)
    waiter.start()
    _avancar_relogio(relogio_controlado, 700_000, passo_ms=25_000)
    bruto = _bruto(fila, job_id)
    assert bruto.get("progress_units", 0) >= 2
    assert bruto["estado"] == "processing"
    assert vivo.is_alive()
    assert terminados == []
    assert waiter.is_alive()
    pare.set()
    app._despachar_proximo_job = lambda: None
    if vivo.is_alive():
        vivo.terminate()
    waiter.join(timeout=2)


def test_cancelar_preserva_audio(
    fila_liveness, ctx_spawn, monkeypatch, relogio_controlado
):
    fila, audio, _pasta = fila_liveness
    ctx, processos, waiters = ctx_spawn
    job1 = fila.enfileirar(audio, None, "job-cancela", {})
    job2 = fila.enfileirar(audio, None, "job-seguinte", {})
    pronto = ctx.Event()
    coop = ctx.Process(
        target=alvos.cooperativo,
        args=(str(fila.pasta_transcricoes), job1, pronto),
    )
    coop.start()
    processos.append(coop)
    assert pronto.wait(10)
    worker = _ProcWorker(coop, [])
    app = _app(fila, relogio_controlado)
    despachados: list[str] = []

    def iniciar(job_id):
        despachados.append(job_id)
        return _WorkerMorto()

    monkeypatch.setattr(app_processamento, "iniciar_subprocesso", iniciar)
    monkeypatch.setattr(app_processamento, "notificar", lambda *a, **k: None)
    app._worker_processamento = worker

    waiter = threading.Thread(
        target=app._aguardar_worker, args=(job1, worker), daemon=True
    )
    waiters.append(waiter)
    waiter.start()
    fila.solicitar_cancelamento(job1)
    _esperar_waiter(waiter)
    app._despachar_proximo_job = lambda: None

    job = fila.obter(job1)
    bruto = _bruto(fila, job1)
    assert job.estado == "cancelled"
    assert job.estado != "ready"
    assert Path(audio).is_file()
    assert bruto.get("erro_seguro")
    assert job2 in despachados


def test_retry_tem_limite(
    fila_liveness, ctx_spawn, monkeypatch, relogio_controlado
):
    fila, audio, _pasta = fila_liveness
    ctx, processos, _waiters = ctx_spawn
    job1 = fila.enfileirar(audio, None, "job-retry", {})
    job2 = fila.enfileirar(audio, None, "job-proximo", {})
    despachados: list[str] = []
    app = _app(fila, relogio_controlado)

    def iniciar(job_id):
        despachados.append(job_id)
        proc = ctx.Process(
            target=alvos.falha_apos_claim,
            args=(str(fila.pasta_transcricoes), job_id),
        )
        proc.start()
        processos.append(proc)
        return _ProcWorker(proc, [])

    monkeypatch.setattr(app_processamento, "iniciar_subprocesso", iniciar)
    monkeypatch.setattr(app_processamento, "notificar", lambda *a, **k: None)

    app._despachar_proximo_job()
    deadline = time.time() + 8
    while time.time() < deadline:
        if (
            fila.obter(job1).estado == "failed"
            and _bruto(fila, job1).get("attempt", 0) >= 2
            and job2 in despachados
        ):
            break
        time.sleep(0.05)

    app._despachar_proximo_job = lambda: None
    bruto = _bruto(fila, job1)
    assert bruto.get("attempt") == 2
    assert fila.obter(job1).estado == "failed"
    assert bruto.get("erro_seguro")
    assert Path(audio).is_file()
    assert despachados.count(job1) == 2
    assert job2 in despachados
    assert despachados.count(job1) <= 2


def test_falha_import_antes_do_claim_nao_reinicia_infinito(
    fila_liveness, ctx_spawn, monkeypatch, relogio_controlado
):
    fila, audio, _pasta = fila_liveness
    ctx, processos, _waiters = ctx_spawn
    job1 = fila.enfileirar(audio, None, "job-import", {})
    job2 = fila.enfileirar(audio, None, "job-depois", {})
    despachados: list[str] = []
    app = _app(fila, relogio_controlado)

    def iniciar(job_id):
        despachados.append(job_id)
        proc = ctx.Process(target=alvos.sai_sem_claim, args=())
        proc.start()
        processos.append(proc)
        return _ProcWorker(proc, [])

    monkeypatch.setattr(app_processamento, "iniciar_subprocesso", iniciar)
    monkeypatch.setattr(app_processamento, "notificar", lambda *a, **k: None)

    app._despachar_proximo_job()
    deadline = time.time() + 6
    while time.time() < deadline and (
        fila.obter(job1).estado != "failed" or job2 not in despachados
    ):
        time.sleep(0.05)

    assert despachados.count(job1) <= 2
    job = fila.obter(job1)
    assert job.estado == "failed"
    assert _bruto(fila, job1).get("erro_seguro")
    assert Path(audio).is_file()
    assert job2 in despachados
    assert len(despachados) < 8
    app._despachar_proximo_job = lambda: None
