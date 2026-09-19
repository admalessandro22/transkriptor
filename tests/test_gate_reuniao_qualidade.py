"""T-13.A2 — qualidade lexical do gate de reunião.

Os casos usam somente TXT sintético e nunca chamam TTS, loopback ou Whisper.
"""
from __future__ import annotations

import importlib.util
import socket
import wave
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
CAMINHO_GATE = REPO / "scripts" / "gate_reuniao_real.py"


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("gate_reuniao_qualidade", CAMINHO_GATE)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def checar(gate, monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "etapa", lambda _nome, ok, _detalhe="": ok)

    def executar(texto: str) -> bool:
        caminho = tmp_path / "resultado.txt"
        caminho.write_text(texto, encoding="utf-8")
        return gate.checar_texto(caminho)

    return executar


def test_cabecalho_nao_e_fala(checar):
    assert not checar(
        "=== Transcricao da reuniao ===\n"
        "Inicio: 2026-09-19T12:00:00Z\n"
        "Fim: 2026-09-19T12:01:00Z\n"
        "Duracao: 1 minuto\n"
        "Origem: gate\n"
        "\n=== Fim ===\n"
    )


def test_ausencia_de_fala_reprova(checar):
    assert not checar(
        "=== Transcricao da reuniao ===\n"
        "Origem: gate\n\n"
        "[00:00:00] (nenhuma fala reconhecida)\n\n=== Fim ===\n"
    )


def test_frase_esperada_precisa_aparecer(checar, gate):
    assert checar(f"=== Transcricao da reuniao ===\n\n[00:00:00] {gate.FRASE}\n")
    assert not checar(
        "=== Transcricao da reuniao ===\n\n"
        "[00:00:00] esta e uma frase diferente da locucao de teste\n"
    )


def test_relogio_controlado_avanca_sem_espera_real(relogio_controlado):
    inicio = relogio_controlado.monotonic_ns()
    relogio_controlado.avancar_ms(1500)
    assert relogio_controlado.monotonic_ns() == inicio + 1_500_000_000


def test_wav_sintetico_tem_formato_explicitamente_controlado(wav_sintetico):
    caminho = wav_sintetico("loopback", frames=320, sample_rate=16_000)
    with wave.open(str(caminho), "rb") as arquivo:
        assert arquivo.getframerate() == 16_000
        assert arquivo.getnframes() == 320
        assert arquivo.getnchannels() == 1


def test_servidor_temporario_fecha_thread_e_socket(servidor_temporario):
    servidor = servidor_temporario(resposta=b"ok")
    with socket.create_connection((servidor.host, servidor.porta), timeout=1) as cliente:
        cliente.sendall(b"ping")
        assert cliente.recv(16) == b"ok"

    servidor.fechar()
    assert not servidor.thread.is_alive()
