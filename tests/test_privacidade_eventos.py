# -*- coding: utf-8 -*-
"""T-13.E4 — eventos tipados, diagnóstico sem PII e ciclo de biometria opt-in."""
from __future__ import annotations

import logging

import pytest

CANARIO = "CANARIO-SINTETICO-7F3A9"


def test_fala_com_prefixo_de_sistema_nao_vaza_em_evento():
    from status_seguro import emitir_evento

    for fala in (
        f"Erro: {CANARIO} precisa sair do log",
        f"Reunião {CANARIO} ontem à noite",
        f"leia {CANARIO}.txt em voz alta",
    ):
        texto = emitir_evento("transcricao_bloco", detalhe=fala)
        assert CANARIO not in texto


def test_status_livre_com_prefixo_operacional_nao_vaza():
    from status_seguro import sanitizar_para_log

    for mensagem in (
        f"Erro ao iniciar: {CANARIO}",
        f"Diarização concluída: {CANARIO}.txt",
        f"Carregando modelo {CANARIO}...",
        f"Gravação {CANARIO} em andamento",
    ):
        assert CANARIO not in sanitizar_para_log(mensagem)


def test_status_real_nao_loga_titulo(modulo_transkriptor, caplog):
    app = modulo_transkriptor.AppTranskriptor.__new__(modulo_transkriptor.AppTranskriptor)
    app.icone = None
    with caplog.at_level(logging.INFO):
        app._status(f"Reunião detectada (janela) — {CANARIO}. Iniciando gravação...")
    assert CANARIO not in caplog.text
    assert "meeting_detected" in caplog.text


def test_falha_ao_apagar_audio_nao_loga_caminho(monkeypatch, caplog):
    import transcricao_core

    monkeypatch.setattr(transcricao_core.os.path, "isfile", lambda _c: True)
    monkeypatch.setattr(transcricao_core.os, "remove", lambda _c: (_ for _ in ()).throw(OSError("falha")))
    with caplog.at_level(logging.WARNING):
        transcricao_core.Transcritor._apagar_descartados(object(), f"C:/Users/{CANARIO}/reuniao.wav")
    assert CANARIO not in caplog.text


def test_erro_critico_nao_loga_mensagem_livre(monkeypatch, caplog):
    import app_ciclo_reuniao

    class _App(app_ciclo_reuniao.CicloReuniaoMixin):
        def _status(self, _msg):
            pass

        def _atualizar_tooltip(self):
            pass

    class _Thread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(app_ciclo_reuniao.threading, "Thread", _Thread)
    monkeypatch.setattr(app_ciclo_reuniao, "notificar", lambda *_a: None)
    with caplog.at_level(logging.ERROR):
        _App()._erro_critico(CANARIO)
    assert CANARIO not in caplog.text


def test_fallback_gpu_nao_loga_excecao(monkeypatch, caplog):
    from types import SimpleNamespace

    import transcricao_core

    monkeypatch.setattr(transcricao_core, "detectar_cuda_e_vram", lambda: (True, 8))
    monkeypatch.setattr(transcricao_core, "resolver_modelo_whisper", lambda *_a: ("large", "cuda", "float16"))
    chamadas = []

    def modelo(*_a, **_k):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError(CANARIO)
        return object()

    monkeypatch.setattr(transcricao_core, "WhisperModel", modelo)
    transcritor = SimpleNamespace(_modelo=None, modelo_nome="auto", on_status=lambda _m: None)
    with caplog.at_level(logging.WARNING):
        transcricao_core.Transcritor._carregar_modelo(transcritor)
    assert len(chamadas) == 2
    assert CANARIO not in caplog.text


def test_modo_somente_audio_nao_loga_excecao(monkeypatch, caplog):
    from types import SimpleNamespace

    import transcricao_core

    class _Thread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(transcricao_core.threading, "Thread", _Thread)
    transcritor = SimpleNamespace(
        rodando=False, _checar_disco_livre=lambda: None, _abrir_arquivo=lambda: None,
        _stop=SimpleNamespace(clear=lambda: None), _resetar_metricas_captura=lambda: None,
        processar_ao_vivo=True, capturar_mic=False, _capturar=lambda: None,
        _processar_somente_audio=lambda: None,
        _carregar_modelo=lambda: (_ for _ in ()).throw(RuntimeError(CANARIO)),
        on_status=lambda _m: None,
    )
    with caplog.at_level(logging.WARNING):
        transcricao_core.Transcritor.start(transcritor)
    assert CANARIO not in caplog.text


def test_excecao_com_token_nao_vaza():
    from status_seguro import sanitizar_excecao

    try:
        raise RuntimeError("falha com token=segredo-abc-123 e sess-tok-xyz")
    except RuntimeError as exc:
        texto = sanitizar_excecao(exc)
    assert "segredo-abc-123" not in texto
    assert "sess-tok-xyz" not in texto
    assert "token" in texto.lower() or "credencial" in texto.lower()


def test_evento_tipado_so_aceita_campos_permitidos():
    from status_seguro import emitir_evento

    texto = emitir_evento("captura_iniciada", dispositivo="loopback", frames=16000)
    assert "captura_iniciada" in texto and "16000" in texto
    with pytest.raises(ValueError):
        emitir_evento("codigo-inexistente")
    with pytest.raises(ValueError):
        emitir_evento("captura_iniciada", texto_livre="fala aqui")
    with pytest.raises(ValueError):
        emitir_evento("captura_iniciada", dispositivo=CANARIO)
    assert "fontes=titulo,extensao" in emitir_evento("meeting_detected", fontes="titulo,extensao")
    with pytest.raises(ValueError):
        emitir_evento("meeting_detected", fontes=f"titulo,{CANARIO}")


def test_diagnostico_exportado_sem_pii(tmp_path, monkeypatch):
    import diagnostico
    from diagnostico import exportar_diagnostico

    monkeypatch.setenv("USERPROFILE", f"C:\\Users\\{CANARIO}")
    itens = [
        {"nome": "Fonte: titulo", "estado": "OK", "detalhe": f"detectou — Reunião {CANARIO} Silva"},
        {"nome": "Zoom", "estado": "OK", "detalhe": "motivo com token=segredo-1"},
        {"nome": "Log completo", "estado": "OK", "detalhe": f"C:\\Users\\{CANARIO}\\AppData\\x.log"},
    ]
    texto = exportar_diagnostico(itens)
    assert CANARIO not in texto
    assert "segredo-1" not in texto
    assert "detectou" in texto


def test_voz_desligada_por_padrao_sem_optin():
    from perfil_voz_flow import cadastrar_perfil_voz

    ok = cadastrar_perfil_voz(finalidade="", consentimento=False)
    assert ok is False


def test_cadastro_exige_finalidade_e_consentimento():
    import perfil_voz_flow

    assert "finalidade" in perfil_voz_flow.cadastrar_perfil_voz.__code__.co_varnames
    assert "consentimento" in perfil_voz_flow.cadastrar_perfil_voz.__code__.co_varnames


def test_correcao_nominal_sem_cadastro(tmp_path):
    from renomear_falante_flow import corrigir_nome_reuniao
    from resultado_reuniao import salvar_segmentos, SegmentoResultado

    caminho = tmp_path / "r.json"
    salvar_segmentos(caminho, [SegmentoResultado("s1", 0, 1000, "loopback", "oi", "FALANTE_00")], {})
    corrigir_nome_reuniao(str(caminho), "rev-1", "FALANTE_00", "Ana", autor="teste")
    assert list(tmp_path.glob("*.npz")) == []
    assert list(tmp_path.glob("*.enc")) == []


def test_revogacao_remove_so_perfil_e_confirma_ausencia(tmp_path):
    from identificador_voz import carregar_perfil
    from perfil_voz_flow import apagar_arquivos_perfil, revogar_perfil_voz

    npz, enc = tmp_path / "perfil.npz", tmp_path / "perfil.enc"
    npz.write_bytes(b"perfil")
    enc.write_bytes(b"cifrado")
    outro = tmp_path / "outro_perfil.npz"
    outro.write_bytes(b"outro")
    assert revogar_perfil_voz(str(npz), str(enc)) is True
    assert not npz.exists() and not enc.exists()
    assert outro.is_file()
    assert carregar_perfil(str(npz), str(enc)) is None


def test_retencao_sem_exclusao_automatica(tmp_path):
    from retencao_audio import inventariar_audios_vencidos

    pasta = tmp_path / "audio"
    pasta.mkdir()
    elegiveis, _ = inventariar_audios_vencidos(pasta, tmp_path, jobs=[], dias=7)
    assert elegiveis == []


def test_canario_fora_de_job_e_log(tmp_path, caplog):
    from fila_processamento import FilaProcessamento

    fila = FilaProcessamento(str(tmp_path))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError):
            fila.enfileirar(None, None, "base??", {"origem": CANARIO, "titulo_reuniao": CANARIO})
    combinado = "\n".join(r.getMessage() for r in caplog.records)
    assert CANARIO not in combinado
