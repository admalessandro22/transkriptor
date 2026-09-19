"""FR-13.B2 — retenção somente após manifesto íntegro e confirmação exata."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from artefatos import criar_referencia, sha256_arquivo
from resultado_reuniao import ResultManifest, StageState, salvar_manifesto, validar_manifesto
from retencao_audio import (
    aplicar_exclusao_confirmada,
    inventariar_audios_vencidos,
    limpar_audios_vencidos,
    pode_expirar,
)


AGORA = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _audio(root, nome="reuniao.wav"):
    pasta = root / "audio"
    pasta.mkdir(exist_ok=True)
    caminho = pasta / nome
    caminho.write_bytes(b"RIFF" + nome.encode("utf-8") + b"\0" * 128)
    return caminho


def _manifesto(root, audio, *, criado_em, estado_stt=StageState.COMPLETE, avisos=()):
    texto = root / "reuniao.txt"
    texto.write_text("[00:00:00] fala sintética", encoding="utf-8")
    referencia = criar_referencia(
        texto, root, format="text/plain", schema_version=1
    )
    manifesto = ResultManifest(
        meeting_id="reuniao-sintetica",
        schema_version=1,
        source_audio_hashes=(sha256_arquivo(audio),),
        participants_ref=None,
        segments_ref=referencia,
        stage_status={"stt": estado_stt},
        warnings=tuple(avisos),
        exports=(referencia,),
        created_at=criado_em.isoformat(),
        pipeline_version="teste",
    )
    caminho = root / "reuniao.resultado.json"
    salvar_manifesto(caminho, manifesto)
    assert validar_manifesto(caminho, root)
    return caminho, texto


def test_cabecalho_nao_libera_audio(tmp_path):
    audio = _audio(tmp_path)
    (tmp_path / "reuniao.txt").write_text(
        "=== Transcricao da reuniao ===\n=== Fim ===\n", encoding="utf-8"
    )

    elegiveis, bloqueados = inventariar_audios_vencidos(
        tmp_path / "audio", tmp_path, agora=AGORA
    )

    assert elegiveis == []
    assert bloqueados == [str(audio)]
    assert audio.is_file()


def test_job_pending_bloqueia_retencao(tmp_path):
    audio = _audio(tmp_path)
    manifesto, _texto = _manifesto(
        tmp_path, audio, criado_em=AGORA - timedelta(days=8)
    )
    job = SimpleNamespace(estado="pending", audio=str(audio))

    assert pode_expirar(audio, [job], manifesto, AGORA) is False
    assert audio.is_file()


def test_hash_divergente_preserva_original(tmp_path):
    audio = _audio(tmp_path)
    manifesto, texto = _manifesto(
        tmp_path, audio, criado_em=AGORA - timedelta(days=8)
    )
    texto.write_text("resultado alterado", encoding="utf-8")

    assert validar_manifesto(manifesto, tmp_path) is False
    assert pode_expirar(audio, [], manifesto, AGORA) is False
    assert audio.is_file()


def test_antes_de_sete_dias_preserva_audio(tmp_path):
    audio = _audio(tmp_path)
    manifesto, _texto = _manifesto(
        tmp_path, audio, criado_em=AGORA - timedelta(days=6, hours=23)
    )

    assert pode_expirar(audio, [], manifesto, AGORA) is False
    assert audio.is_file()


def test_resultado_confirmado_apos_sete_dias_libera_so_alvo(tmp_path):
    alvo = _audio(tmp_path, "alvo.wav")
    preservado = _audio(tmp_path, "preservado.wav")
    _manifesto(tmp_path, alvo, criado_em=AGORA - timedelta(days=7))

    elegiveis, bloqueados = inventariar_audios_vencidos(
        tmp_path / "audio", tmp_path, agora=AGORA
    )
    assert elegiveis == [str(alvo)]
    assert bloqueados == [str(preservado)]

    previsao = aplicar_exclusao_confirmada(
        elegiveis,
        pasta_audio=tmp_path / "audio",
        confirmados=[str(alvo)],
        dry_run=True,
    )
    assert previsao == [str(alvo)]
    assert alvo.is_file()

    removidos = aplicar_exclusao_confirmada(
        elegiveis,
        pasta_audio=tmp_path / "audio",
        confirmados=[str(alvo)],
        dry_run=False,
    )
    assert removidos == [str(alvo)]
    assert not alvo.exists()
    assert preservado.is_file()


def test_resultado_nao_expira_automaticamente(tmp_path):
    audio = _audio(tmp_path)
    manifesto, _texto = _manifesto(
        tmp_path, audio, criado_em=AGORA - timedelta(days=8)
    )
    elegiveis, _bloqueados = inventariar_audios_vencidos(
        tmp_path / "audio", tmp_path, agora=AGORA
    )

    aplicar_exclusao_confirmada(
        elegiveis,
        pasta_audio=tmp_path / "audio",
        confirmados=[str(audio)],
        dry_run=False,
    )

    assert manifesto.is_file()


def test_manifesto_valido_ainda_no_prazo_nao_vira_orfao(tmp_path):
    audio = _audio(tmp_path)
    _manifesto(tmp_path, audio, criado_em=AGORA - timedelta(days=2))

    removidos, orfaos = limpar_audios_vencidos(
        str(tmp_path / "audio"), str(tmp_path), agora=AGORA
    )

    assert removidos == []
    assert orfaos == []
    assert audio.is_file()


def test_confirmacao_nao_remove_audio_fora_do_inventario(tmp_path):
    pasta_audio = tmp_path / "audio"
    pasta_audio.mkdir()
    externo = tmp_path / "fora.wav"
    externo.write_bytes(b"RIFF-fora")

    removidos = aplicar_exclusao_confirmada(
        [str(externo)],
        confirmados=[str(externo)],
        dry_run=False,
        pasta_audio=pasta_audio,
    )

    assert removidos == []
    assert externo.is_file()


def test_stt_sem_fala_nao_e_resultado_util_para_retencao(tmp_path):
    audio = _audio(tmp_path)
    manifesto, _texto = _manifesto(
        tmp_path,
        audio,
        criado_em=AGORA - timedelta(days=8),
        estado_stt=StageState.PARTIAL,
        avisos=("stt_sem_fala",),
    )

    assert pode_expirar(audio, [], manifesto, AGORA) is False
