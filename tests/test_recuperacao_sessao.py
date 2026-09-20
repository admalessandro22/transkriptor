# -*- coding: utf-8 -*-
"""T-13.E2 — inventário e recuperação por sessão, sem tocar sessão viva."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path

import pytest

from recuperacao_sessao import (
    finalizar_sessao,
    inventariar,
    recuperar,
    registrar_ativo,
    registrar_inicio,
    tem_escritor_vivo,
)


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _raiz(tmp_path: Path) -> Path:
    raiz = tmp_path / "rec"
    raiz.mkdir()
    return raiz


def test_crash_antes_do_move_recupera(tmp_path):
    """WAV ainda na pasta de trabalho volta para a sessão; hash intacto."""
    raiz = _raiz(tmp_path)
    registrar_inicio(raiz, "sess-1")
    trabalho = raiz / "trabalho"
    trabalho.mkdir()
    wav = trabalho / "reuniao_audio.wav"
    wav.write_bytes(b"RIFF" + b"\x01" * 1000)
    registrar_ativo(raiz, "sess-1", str(wav))
    antes = _sha(wav)
    itens = inventariar(raiz, set())
    assert any(i.action == "recuperar_mover" and i.owner_session_id == "sess-1" for i in itens)
    planejados = recuperar(raiz, itens, dry_run=True)
    assert wav.is_file()
    feitos = recuperar(raiz, planejados, dry_run=False)
    destino = raiz / "sessoes" / "sess-1" / "audio" / "reuniao_audio.wav"
    assert destino.is_file()
    assert _sha(destino) == antes
    assert feitos[0].state == "recuperado"


def test_crash_durante_diarizacao_recupera_legado(tmp_path):
    """Dir diarizacao_* órfão é recolhido; hash do original permanece."""
    raiz = _raiz(tmp_path)
    legado = raiz / "diarizacao_abc123"
    legado.mkdir()
    wav = legado / "base_audio.wav"
    wav.write_bytes(b"RIFF" + b"\x02" * 500)
    antes = _sha(wav)
    itens = inventariar(raiz, set())
    assert any("diarizacao_abc123" in i.relative_path for i in itens)
    recuperar(raiz, itens, dry_run=False)
    destino = raiz / "sessoes" / "recuperado-legado" / "base_audio.wav"
    assert destino.is_file() and _sha(destino) == antes


def test_apos_cifra_antes_do_unlink_preserva_unica_copia(tmp_path, chave_teste):
    """Par .wav + .wav.enc em área de trabalho: plaintext só sai validado."""
    from crypto_storage import criptografar_wav

    raiz = _raiz(tmp_path)
    pasta = raiz / "trabalho"
    pasta.mkdir()
    wav = pasta / "r_audio.wav"
    wav.write_bytes(b"RIFF" + b"\x03" * 200)
    enc = criptografar_wav(str(wav))
    assert enc.endswith(".wav.enc")
    # Simula queda entre cifra e unlink: ambos presentes.
    (pasta / "r_audio.wav").write_bytes(b"RIFF" + b"\x03" * 200)
    itens = inventariar(raiz, set())
    assert wav.is_file()
    recuperar(raiz, itens, dry_run=True)
    assert wav.is_file()
    recuperar(raiz, itens, dry_run=False)
    assert not wav.exists()
    assert Path(enc).is_file()


def test_sessao_viva_preservada(tmp_path):
    """Sessão viva: inventário sinaliza, recuperação não toca."""
    raiz = _raiz(tmp_path)
    registrar_inicio(raiz, "sess-viva")
    wav = raiz / "sessoes" / "sess-viva" / "audio.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(b"RIFF" + b"\x04" * 100)
    itens = inventariar(raiz, {"sess-viva"})
    assert itens and all(i.action == "preservar_viva" for i in itens)
    recuperar(raiz, itens, dry_run=False)
    assert wav.is_file()


def test_junction_externo_recusado(tmp_path):
    """Symlink para fora da raiz: recusado, nunca seguido."""
    alvo_dir = tmp_path / "fora"
    alvo_dir.mkdir()
    (alvo_dir / "secreto.wav").write_bytes(b"RIFF")
    raiz = _raiz(tmp_path)
    elo = raiz / "audio" / "atalho.wav"
    elo.parent.mkdir(parents=True, exist_ok=True)
    try:
        elo.symlink_to(alvo_dir / "secreto.wav")
    except OSError:
        pytest.skip("sem privilégio de symlink")
    itens = inventariar(raiz, set())
    alvos = [i for i in itens if "atalho" in i.relative_path]
    assert alvos and alvos[0].action == "recusar_externo"
    recuperar(raiz, itens, dry_run=False)
    assert (alvo_dir / "secreto.wav").is_file()


def test_desconhecido_parecido_sinalizado(tmp_path):
    """Arquivo fora dos padrões conhecidos: sinalizado, nunca removido."""
    raiz = _raiz(tmp_path)
    estranho = raiz / "reuniao_backup.wav"
    estranho.write_bytes(b"RIFF" + b"\x05" * 100)
    itens = inventariar(raiz, set())
    alvos = [i for i in itens if "reuniao_backup" in i.relative_path]
    assert alvos and alvos[0].action == "sinalizar"
    recuperar(raiz, itens, dry_run=False)
    assert estranho.is_file()


def test_escritor_vivo_bloqueia_e_morto_libera(tmp_path):
    """Lease de processo vivo bloqueia; subprocesso terminado libera."""
    import gc

    from fila_lock import current_process_identity

    vivo = {"owner": {"pid": current_process_identity().pid,
                      "created_at_100ns": current_process_identity().created_at_100ns}}
    assert tem_escritor_vivo(vivo) is True
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        from fila_lock import _created_at_100ns

        dono = {"owner": {"pid": proc.pid, "created_at_100ns": _created_at_100ns(proc.pid)}}
        assert tem_escritor_vivo(dono) is True
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    del proc
    gc.collect()
    for _ in range(100):
        if tem_escritor_vivo(dono) is False:
            break
        time.sleep(0.05)
    assert tem_escritor_vivo(dono) is False
