# -*- coding: utf-8 -*-
"""NFR-10.H3/SEC-10.F4 — rastreabilidade segura do worker posterior."""
from __future__ import annotations

import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from fila_processamento import FilaProcessamento


def test_ciclo_do_worker_persiste_metadados_sem_fala(tmp_path):
    pasta = tmp_path / "transcricoes"
    audio_dir = pasta / "audio"
    audio_dir.mkdir(parents=True)
    audio = audio_dir / "reuniao.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    fila = FilaProcessamento(str(pasta))
    job_id = fila.enfileirar(
        str(audio), None, "reuniao", {"origem": "meet", "texto": "fala secreta"}
    )

    fila.registrar_worker(job_id, pid=4321, iniciado_em="2026-08-10T14:00:00+00:00")
    fila.registrar_saida_worker(
        job_id,
        codigo=0,
        terminado_em="2026-08-10T14:00:05+00:00",
    )

    job = fila.obter(job_id)
    bruto = json.loads(fila.caminho_job(job_id).read_text(encoding="utf-8"))
    assert job.worker_pid == 4321
    assert job.worker_codigo_saida == 0
    assert job.worker_iniciado_em == "2026-08-10T14:00:00+00:00"
    assert job.worker_terminado_em == "2026-08-10T14:00:05+00:00"
    assert "fala secreta" not in json.dumps(bruto, ensure_ascii=False)
    assert audio.is_file()


def test_aguardar_worker_registra_saida_e_preserva_job_pendente(
    tmp_path, monkeypatch
):
    import app_processamento

    pasta = tmp_path / "transcricoes"
    audio_dir = pasta / "audio"
    audio_dir.mkdir(parents=True)
    audio = audio_dir / "reuniao.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    fila = FilaProcessamento(str(pasta))
    job_id = fila.enfileirar(str(audio), None, "reuniao", {})
    worker = SimpleNamespace(pid=9876, wait=lambda: 7)
    fila.registrar_worker(job_id, pid=9876, iniciado_em="2026-08-10T14:00:00+00:00")

    app = app_processamento.ProcessamentoReuniaoMixin.__new__(
        app_processamento.ProcessamentoReuniaoMixin
    )
    app._lock = threading.Lock()
    app._worker_processamento = worker
    app._estado_processamento = "Processando"
    app._ultimo_job_id = job_id
    app.fila = fila
    app._atualizar_tooltip = lambda: None
    app._despachar_proximo_job = MagicMock()
    monkeypatch.setattr(app_processamento, "notificar", lambda *args, **kwargs: None)

    app._aguardar_worker(job_id, worker)

    job = fila.obter(job_id)
    assert job.worker_pid == 9876
    assert job.worker_codigo_saida == 7
    assert job.worker_terminado_em
    assert job.estado == "pending"
    assert audio.is_file()
    app._despachar_proximo_job.assert_not_called()


def test_despacho_registra_pid_do_worker(tmp_path, monkeypatch):
    import app_processamento

    pasta = tmp_path / "transcricoes"
    audio_dir = pasta / "audio"
    audio_dir.mkdir(parents=True)
    audio = audio_dir / "reuniao.wav"
    audio.write_bytes(b"RIFF" + b"\0" * 64)
    fila = FilaProcessamento(str(pasta))
    job_id = fila.enfileirar(str(audio), None, "reuniao", {})

    class Worker:
        pid = 2468

        def poll(self):
            return None

    class ThreadNaoInicia:
        def __init__(self, *, target, args, daemon, name):
            self.target = target
            self.args = args

        def start(self):
            return None

    app = app_processamento.ProcessamentoReuniaoMixin.__new__(
        app_processamento.ProcessamentoReuniaoMixin
    )
    app._lock = threading.Lock()
    app._worker_processamento = None
    app._estado_processamento = None
    app._ultimo_job_id = None
    app.fila = fila
    app._atualizar_tooltip = lambda: None
    monkeypatch.setattr(app_processamento, "iniciar_subprocesso", lambda _id: Worker())
    monkeypatch.setattr(app_processamento.threading, "Thread", ThreadNaoInicia)

    app._despachar_proximo_job()

    job = fila.obter(job_id)
    assert job.worker_pid == 2468
    assert job.worker_iniciado_em
    assert app._estado_processamento == "Processando"
