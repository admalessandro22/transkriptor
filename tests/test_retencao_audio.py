# -*- coding: utf-8 -*-
"""T-F2-03 — retenção de áudios (FR-2.3)."""
from datetime import datetime, timedelta
from pathlib import Path

from retencao_audio import limpar_audios_vencidos


def _tocar_mtime(path: Path, quando: datetime):
    ts = quando.timestamp()
    import os

    os.utime(path, (ts, ts))


def test_audio_com_txt_sem_manifesto_permanece_em_dry_run(tmp_path):
    pasta_audio = tmp_path / "audio"
    pasta_tr = tmp_path / "tr"
    pasta_audio.mkdir()
    pasta_tr.mkdir()
    base = "transcricao_2026-07-01_10h00"
    wav = pasta_audio / f"{base}_audio.wav"
    wav.write_bytes(b"RIFF")
    (pasta_tr / f"{base}.txt").write_text("ok", encoding="utf-8")
    agora = datetime(2026, 7, 19, 12, 0, 0)
    _tocar_mtime(wav, agora - timedelta(days=8))

    removidos, orfaos = limpar_audios_vencidos(
        str(pasta_audio), str(pasta_tr), dias=7, agora=agora
    )
    assert removidos == []
    assert orfaos == [str(wav)]
    assert wav.exists()


def test_audio_8_dias_sem_transcricao_mantido_e_reportado(tmp_path):
    pasta_audio = tmp_path / "audio"
    pasta_tr = tmp_path / "tr"
    pasta_audio.mkdir()
    pasta_tr.mkdir()
    wav = pasta_audio / "transcricao_2026-07-01_10h00_audio.wav.enc"
    wav.write_bytes(b"enc")
    agora = datetime(2026, 7, 19, 12, 0, 0)
    _tocar_mtime(wav, agora - timedelta(days=8))

    removidos, orfaos = limpar_audios_vencidos(
        str(pasta_audio), str(pasta_tr), dias=7, agora=agora
    )
    assert removidos == []
    assert orfaos == [str(wav)]
    assert wav.exists()


def test_audio_recente_sem_manifesto_permanece_em_dry_run(tmp_path):
    pasta_audio = tmp_path / "audio"
    pasta_tr = tmp_path / "tr"
    pasta_audio.mkdir()
    pasta_tr.mkdir()
    base = "transcricao_2026-07-17_10h00"
    wav = pasta_audio / f"{base}_audio.wav"
    wav.write_bytes(b"x")
    (pasta_tr / f"{base}.tkpt").write_bytes(b"t")
    agora = datetime(2026, 7, 19, 12, 0, 0)
    _tocar_mtime(wav, agora - timedelta(days=2))

    removidos, orfaos = limpar_audios_vencidos(
        str(pasta_audio), str(pasta_tr), dias=7, agora=agora
    )
    assert removidos == []
    assert orfaos == [str(wav)]
    assert wav.exists()


def test_tkas_sem_manifesto_entra_no_inventario_sem_exclusao(tmp_path):
    from retencao_audio import inventariar_audios_vencidos

    pasta_audio = tmp_path / "audio"
    pasta_tr = tmp_path / "tr"
    pasta_audio.mkdir()
    pasta_tr.mkdir()
    tks = pasta_audio / "reuniao_audio.tks"
    tks.write_bytes(b"TKAS")
    elegiveis, bloqueados = inventariar_audios_vencidos(pasta_audio, pasta_tr, jobs=[])
    assert elegiveis == []
    assert bloqueados == [str(tks)]


def test_constante_retencao_7_dias():
    from config import RETENCAO_AUDIO_DIAS

    assert RETENCAO_AUDIO_DIAS == 7
