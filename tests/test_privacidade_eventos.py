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
