# -*- coding: utf-8 -*-
"""A parada real do ciclo entrega os segmentos Meet ao job durável."""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app_ciclo_reuniao import CicloReuniaoMixin
from app_processamento import ProcessamentoReuniaoMixin
from eventos_meet_store import EventStore
from fila_processamento import FilaProcessamento
from sessao_reuniao import criar_sessao


@pytest.fixture
def app_com_store(tmp_path, chave_teste):
    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    audio = raiz / "audio" / "reuniao.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"RIFF" + b"\x00" * 64)
    sessao = criar_sessao("meet-opaca", "2026-09-19T20:00:00Z", "padrao")
    store = EventStore(raiz / "eventos_privados", sessao, ancora_refs=raiz)
    store.append({
        "schema_version": 1,
        "event_id": "evento-1",
        "session_id": sessao.session_id,
        "connection_id": "conexao-1",
        "seq": 0,
        "tab_id": "aba-1",
        "meeting_key": sessao.meeting_key,
        "kind": "caption",
        "client_wall_ms": int(time.time() * 1000),
        "client_monotonic_ms": 1000,
        "received_monotonic_ns": time.monotonic_ns(),
        "display_name": "Ana",
        "text": "fala sintética",
    })

    class App(CicloReuniaoMixin, ProcessamentoReuniaoMixin):
        def __init__(self):
            self._lock = threading.Lock()
            self.watchdog = None
            self.fila = FilaProcessamento(str(raiz))
            self._sessao_ativa = sessao
            self._eventos_store = store
            self._inicio_transcricao_wall_ms = int(time.time() * 1000)
            self._titulo_reuniao_atual = None
            self._estado_processamento = None
            self._ultimo_job_id = None
            self.usar_nomes_meet = False
            self.diarizacao_ativa = False
            self.identificar_minha_voz = False
            self.criptografar_transcricoes = False
            self.modelo_whisper = "small"
            self.meet_bridge = SimpleNamespace(definir_sessao_ativa=lambda *_args: None)
            self.transcritor = SimpleNamespace(
                rodando=True, stop=lambda: str(audio), audios_preservados=[str(audio)],
                modelo_nome="small", idioma="pt",
            )

        def _status(self, _mensagem):
            pass

        def _atualizar_tooltip(self):
            pass

        def _despachar_proximo_job(self):
            pass

    return App(), raiz


def test_parar_sela_e_entrega_refs_ao_job(app_com_store):
    app, raiz = app_com_store
    app._parar_transcricao()
    job = app.fila.listar()[0]
    assert len(job.eventos_refs) == 1
    assert job.eventos_refs[0]["format"] == "meet-events-jsonl-enc"
    assert app._eventos_store is None
    assert app.transcritor is None

    reiniciada = FilaProcessamento(str(raiz))
    assert reiniciada.obter(job.id).eventos_refs == job.eventos_refs


def test_enfileirar_preserva_duas_fontes_tkas(app_com_store, wav_sintetico, chave_teste):
    from diarizacao_final import preservar_audios
    from politica_privacidade import ProtectionMode

    app, raiz = app_com_store
    lb = wav_sintetico("loopback")
    mic = wav_sintetico("microfone")
    lb_nome = lb.with_name("reuniao_audio.wav")
    mic_nome = mic.with_name("reuniao_mic.wav")
    lb.rename(lb_nome)
    mic.rename(mic_nome)
    protegidos = preservar_audios(ProtectionMode.PROTECTED, str(lb_nome), str(mic_nome),
                                  pasta_audio=str(raiz / "audio"))
    app.transcritor.audios_preservados = protegidos
    job_id = app._enfileirar_reuniao(app.transcritor, str(raiz / "reuniao.tkpt"))
    job = app.fila.obter(job_id)
    assert job.audio.endswith("_audio.tks")
    assert job.mic.endswith("_mic.tks")


def test_worker_apos_restart_le_eventos_do_fluxo_real(app_com_store):
    from processador_reuniao import processar_job

    app, raiz = app_com_store
    app._parar_transcricao()
    job = app.fila.listar()[0]
    reiniciada = FilaProcessamento(str(raiz))
    recebido = {}

    def retranscrever_fake(_audio, **kwargs):
        from resultado_pipeline import ResultadoProcessamento

        recebido["eventos"] = kwargs["eventos_meet"]
        saida = raiz / "reuniao.txt"
        return ResultadoProcessamento(saida, ())

    with patch("retranscritor.retranscrever_resultado", side_effect=retranscrever_fake):
        processar_job(job.id, fila=reiniciada)
    assert reiniciada.obter(job.id).estado == "ready"
    assert [evento["display_name"] for evento in recebido["eventos"]] == ["Ana"]


def test_artefato_adulterado_nao_chega_ao_worker(app_com_store):
    from processador_reuniao import processar_job

    app, raiz = app_com_store
    app._parar_transcricao()
    job = app.fila.listar()[0]
    ref = job.eventos_refs[0]
    (raiz / ref["relative_path"]).write_bytes(b"alterado")
    reiniciada = FilaProcessamento(str(raiz))
    recebido = {}

    def retranscrever_fake(_audio, **kwargs):
        from resultado_pipeline import ResultadoProcessamento

        recebido["eventos"] = kwargs["eventos_meet"]
        saida = raiz / "reuniao.txt"
        return ResultadoProcessamento(saida, ())

    with patch("retranscritor.retranscrever_resultado", side_effect=retranscrever_fake):
        processar_job(job.id, fila=reiniciada)
    assert recebido["eventos"] == []
    assert "evento_hash_invalido_recusado" in reiniciada.obter(job.id).warnings
