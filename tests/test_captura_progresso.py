# -*- coding: utf-8 -*-
"""Regressões de progresso e finalização segura da captura (FR-13.C1)."""
from __future__ import annotations

import ast
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

import diagnostico
from transcricao_core import Transcritor
from watchdog import Watchdog


RAIZ = Path(__file__).resolve().parent.parent


def _thread_viva() -> MagicMock:
    thread = MagicMock()
    thread.is_alive.return_value = True
    return thread


def test_thread_viva_sem_frames_gera_erro():
    """Uma thread viva sem frame de loopback não pode parecer captura saudável."""
    erros: list[str] = []
    transcritor = SimpleNamespace(
        rodando=True,
        finalizando=False,
        capturar_mic=False,
        _thread_cap=_thread_viva(),
        _thread_proc=_thread_viva(),
        metricas_captura=lambda: {
            "fontes": {
                "loopback": {
                    "frames": 0,
                    "ultimo_frame_monotonic": time.monotonic() - 11,
                    "erros_consecutivos": 0,
                }
            }
        },
    )

    watchdog = Watchdog(transcritor, on_erro_critico=erros.append)

    watchdog._verificar()

    assert any("loopback" in erro.lower() for erro in erros)


def test_silencio_com_frames_nao_falha(tmp_path):
    """Silêncio é áudio capturado; ausência de frames é que caracteriza falha."""
    erros: list[str] = []
    transcritor = Transcritor(
        pasta_saida=str(tmp_path),
        capturar_mic=False,
        processar_ao_vivo=True,
    )
    transcritor.rodando = True
    transcritor._thread_cap = _thread_viva()
    transcritor._thread_proc = _thread_viva()

    transcritor._enfileirar_audio(np.zeros(16000, dtype=np.float32))

    metricas = transcritor.metricas_captura()
    assert metricas["fontes"]["loopback"]["frames"] == 16000
    watchdog = Watchdog(transcritor, on_erro_critico=erros.append)
    watchdog._verificar()
    assert erros == []


def test_mic_morto_e_supervisionado(tmp_path, monkeypatch):
    """Erros repetidos do microfone são falha de dispositivo, mesmo com thread viva."""
    class RecorderComFalha:
        chamadas = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def record(self, numframes):
            del numframes
            self.chamadas += 1
            if self.chamadas == 3:
                transcritor._stop.set()
            raise OSError("dispositivo removido")

    erros: list[str] = []
    transcritor = Transcritor(pasta_saida=str(tmp_path), capturar_mic=True)
    transcritor.rodando = True
    transcritor._thread_cap = _thread_viva()
    transcritor._thread_proc = _thread_viva()
    transcritor._thread_mic = _thread_viva()
    microfone = MagicMock()
    microfone.recorder.return_value = RecorderComFalha()
    monkeypatch.setattr("captura_leve.sc.default_microphone", lambda: microfone)
    monkeypatch.setattr("captura_leve.time.sleep", lambda _seg: None)

    transcritor._capturar_mic_interno()

    assert transcritor.metricas_captura()["fontes"]["microfone"]["erros_consecutivos"] == 3
    watchdog = Watchdog(transcritor, on_erro_critico=erros.append)
    watchdog._verificar()
    assert any("microfone" in erro.lower() and "dispositivo" in erro.lower() for erro in erros)


def test_cadastro_mantem_com():
    """O cadastro também fala com soundcard e precisa do mesmo contexto COM."""
    arvore = ast.parse(
        (RAIZ / "identificador_voz.py").read_text(encoding="utf-8"),
        filename="identificador_voz.py",
    )
    funcao = next(
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef) and no.name == "gravar_audio_microfone"
    )

    assert any(
        isinstance(no, ast.Call)
        and getattr(no.func, "id", getattr(no.func, "attr", "")) == "com_inicializada"
        for no in ast.walk(funcao)
    )


def test_stop_nao_move_wav_com_escritor_vivo(tmp_path):
    """Timeout no join preserva o WAV aberto e sinaliza finalização pendente."""
    class EscritorAindaVivo:
        def is_alive(self):
            return True

        def join(self, timeout):
            del timeout

    status: list[str] = []
    transcritor = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=False,
        capturar_mic=False,
        criptografar=False,
        on_status=status.append,
    )
    transcritor._abrir_arquivo()
    transcritor.rodando = True
    transcritor._thread_proc = EscritorAindaVivo()
    preservar = MagicMock()
    transcritor._preservar_audios = preservar

    try:
        assert transcritor.stop() is None
        assert transcritor._wav is not None
        preservar.assert_not_called()
        assert any("finaliza" in mensagem.lower() and "pendente" in mensagem.lower() for mensagem in status)
    finally:
        transcritor._fechar_arquivos_abertos()


def test_reinicio_de_dispositivo_delimita_lacuna_no_resultado(tmp_path, chave_teste):
    """A retomada de frames fecha a lacuna registrada no resultado da reunião."""
    status: list[str] = []
    transcritor = Transcritor(
        pasta_saida=str(tmp_path),
        capturar_mic=False,
        on_status=status.append,
        criptografar=False,
    )
    transcritor._abrir_arquivo()
    transcritor.rodando = True
    transcritor._thread_cap = _thread_viva()
    transcritor._thread_proc = _thread_viva()
    with transcritor._metricas_lock:
        transcritor._fontes_captura["loopback"]["ultimo_frame_monotonic"] = time.monotonic() - 11

    try:
        Watchdog(transcritor)._verificar()
        transcritor._enfileirar_audio(np.zeros(160, dtype=np.float32))

        lacuna = transcritor.metricas_captura()["lacunas"][0]
        assert lacuna["fonte"] == "loopback"
        assert lacuna["fim_monotonic"] is not None
        assert "Lacuna de captura: loopback" in Path(transcritor._caminho_saida).read_text(encoding="utf-8")
        assert any("lacuna" in mensagem.lower() for mensagem in status)
    finally:
        transcritor._fechar_arquivos_abertos()


def test_disco_cheio_e_supervisionado(tmp_path, monkeypatch):
    """Disco sem espaço é estado de captura visível, não um aviso genérico."""
    erros: list[str] = []
    transcritor = Transcritor(pasta_saida=str(tmp_path), capturar_mic=False)
    transcritor.rodando = True
    transcritor._thread_cap = _thread_viva()
    transcritor._thread_proc = _thread_viva()
    monkeypatch.setattr(
        "transcricao_core.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=0),
    )

    transcritor._checar_disco_livre()

    assert transcritor.metricas_captura()["disco"]["estado"] == "sem_espaco"
    Watchdog(transcritor, on_erro_critico=erros.append)._verificar()
    assert any("disco" in erro.lower() for erro in erros)


def test_diagnostico_expoe_disco_sem_espaco():
    """O diagnóstico diferencia falta de espaço de uma captura normal."""
    class CapturaComDiscoCheio:
        def metricas_captura(self):
            return {
                "frames_gravados": 16000,
                "falhas_captura": 0,
                "falhas_gravacao": 0,
                "blocos_descartados": 0,
                "disco": {"livre_bytes": 0, "estado": "sem_espaco"},
            }

    item = diagnostico.checar_metricas_captura(CapturaComDiscoCheio())[0]

    assert item["estado"] == diagnostico.ERRO
    assert "disco=sem_espaco" in item["detalhe"]


def test_microfone_desativado_nao_e_supervisionado():
    """A fonte opcional não gera falso alarme se a captura de mic está desligada."""
    erros: list[str] = []
    transcritor = SimpleNamespace(
        rodando=True,
        finalizando=False,
        capturar_mic=False,
        _thread_cap=_thread_viva(),
        _thread_proc=_thread_viva(),
        metricas_captura=lambda: {
            "fontes": {
                "loopback": {
                    "frames": 16000,
                    "ultimo_frame_monotonic": time.monotonic(),
                    "erros_consecutivos": 0,
                },
                "microfone": {
                    "frames": 0,
                    "ultimo_frame_monotonic": time.monotonic() - 11,
                    "erros_consecutivos": 0,
                },
            }
        },
    )

    Watchdog(transcritor, on_erro_critico=erros.append)._verificar()

    assert erros == []


def test_watchdog_reinicia_microfone_morto():
    """A queda da thread opcional tem recuperação própria, sem derrubar o loopback."""
    microfone_morto = MagicMock()
    microfone_morto.is_alive.return_value = False
    reiniciar_microfone = MagicMock()
    transcritor = SimpleNamespace(
        rodando=True,
        finalizando=False,
        capturar_mic=True,
        _thread_cap=_thread_viva(),
        _thread_proc=_thread_viva(),
        _thread_mic=microfone_morto,
        _reiniciar_microfone=reiniciar_microfone,
        metricas_captura=lambda: {
            "fontes": {
                "loopback": {
                    "frames": 16000,
                    "ultimo_frame_monotonic": time.monotonic(),
                    "erros_consecutivos": 0,
                },
                "microfone": {
                    "frames": 16000,
                    "ultimo_frame_monotonic": time.monotonic(),
                    "erros_consecutivos": 0,
                },
            }
        },
    )

    Watchdog(transcritor)._verificar()

    reiniciar_microfone.assert_called_once()


def test_gravacao_atualiza_estado_de_disco(tmp_path, monkeypatch):
    """A verificação de espaço acompanha a escrita, não só o início da reunião."""
    transcritor = Transcritor(
        pasta_saida=str(tmp_path),
        capturar_mic=False,
        criptografar=False,
    )
    transcritor._abrir_arquivo()
    monkeypatch.setattr(
        "transcricao_core.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=0),
    )

    try:
        transcritor._gravar_audio_bloco(np.zeros(160, dtype=np.float32))
        assert transcritor.metricas_captura()["disco"]["estado"] == "sem_espaco"
    finally:
        transcritor._fechar_arquivos_abertos()
