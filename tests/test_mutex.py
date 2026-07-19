# -*- coding: utf-8 -*-
"""Testes de mutex instância única (Fase 2 — FR-2.6)."""
import subprocess
import sys

from transkriptor_lock import _pid_vivo, adquirir_lock, liberar_lock


def test_segundo_lock_falha(tmp_path):
    lock1 = tmp_path / "t.lock"
    assert adquirir_lock(lock1) is True
    assert adquirir_lock(lock1) is False
    liberar_lock()
    assert adquirir_lock(lock1) is True
    liberar_lock()


def test_locks_em_arquivos_diferentes(tmp_path):
    a = tmp_path / "a.lock"
    b = tmp_path / "b.lock"
    assert adquirir_lock(a) is True
    assert adquirir_lock(b) is True
    liberar_lock()
    liberar_lock()


def test_pid_terminado_nao_mantem_lock_ocupado():
    processo = subprocess.Popen([sys.executable, "-c", "pass"])
    pid = processo.pid
    processo.wait(timeout=10)

    assert _pid_vivo(pid) is False
