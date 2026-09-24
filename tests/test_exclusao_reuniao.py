# -*- coding: utf-8 -*-
"""Excluir reunião apaga todos os dados dela e nada além (pedido do usuário, 24/09/2026).

DU-11: nada é removido sem confirmação com a lista exata de alvos — o plano
mostrado é o plano executado (`plano_id`), senão a exclusão é recusada.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import exclusao_reuniao as ex

MID = "a" * 32
VIZINHA = "b" * 32
SESSAO = "11111111-2222-3333-4444-555555555555"


def _reuniao(raiz: Path, mid: str, base: str, sessao: str | None, estado="ready") -> None:
    (raiz / "resultados").mkdir(exist_ok=True)
    (raiz / "audio").mkdir(exist_ok=True)
    (raiz / "resumos").mkdir(exist_ok=True)
    jobs = raiz / ".jobs_processamento"
    (jobs / ".locks").mkdir(parents=True, exist_ok=True)
    (raiz / f"{base}.txt").write_text("fala", encoding="utf-8")
    (raiz / f"{base}.tkpt").write_bytes(b"cifrado")
    (raiz / f"{base}_diarizado.txt").write_text("fala", encoding="utf-8")
    (raiz / "resultados" / f"{mid}.json").write_text("{}", encoding="utf-8")
    (raiz / "audio" / f"{base}_audio.wav.enc").write_bytes(b"x" * 10)
    (raiz / "audio" / f"{base}_mic.wav.enc").write_bytes(b"x" * 10)
    (raiz / "resumos" / f"{mid}.resumo").write_bytes(b"r")
    manifesto = {
        "meeting_id": mid,
        "segments_ref": {"relative_path": f"resultados/{mid}.json"},
        "exports": [{"relative_path": f"{base}.txt"}],
    }
    (raiz / f"{base}.resultado.json").write_text(json.dumps(manifesto), encoding="utf-8")
    job = {"id": mid, "estado": estado, "audio": f"audio/{base}_audio.wav.enc", "mic": f"audio/{base}_mic.wav.enc",
           "base_saida": base, "manifesto_resultado": f"{base}.resultado.json",
           "sessao": {"session_id": sessao} if sessao else None}
    (jobs / f"{mid}.json").write_text(json.dumps(job), encoding="utf-8")
    (jobs / ".locks" / f"{mid}.lock").write_text("", encoding="utf-8")
    if sessao:
        (raiz / "sessoes" / sessao / "audio").mkdir(parents=True)
        (raiz / "sessoes" / sessao / "registro.json").write_text("{}", encoding="utf-8")
        (raiz / "eventos_privados" / sessao).mkdir(parents=True)
        (raiz / "eventos_privados" / sessao / "seg-0001.bin").write_bytes(b"e")
    indice = raiz / "indice.json"
    dados = json.loads(indice.read_text(encoding="utf-8")) if indice.is_file() else {"version": 1, "meetings": {}}
    dados["meetings"][mid] = {"manifest": f"{base}.resultado.json", "title": None}
    indice.write_text(json.dumps(dados), encoding="utf-8")


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "transcricoes"
    r.mkdir()
    _reuniao(r, MID, "transcricao_24-09-26_16h05", SESSAO)
    # vizinha cujo nome começa igual: não pode ser tocada
    _reuniao(r, VIZINHA, "transcricao_24-09-26_16h05_Reuniao_X", "99999999-2222-3333-4444-555555555555")
    return r


def _todos(raiz: Path) -> set[str]:
    return {p.relative_to(raiz).as_posix() for p in raiz.rglob("*")}


def test_plano_lista_tudo_da_reuniao_e_nada_da_vizinha(raiz):
    plano = ex.planejar(raiz, MID)
    caminhos = {i.caminho for i in plano.itens}
    assert caminhos == {
        "transcricao_24-09-26_16h05.resultado.json",
        "transcricao_24-09-26_16h05.txt",
        "transcricao_24-09-26_16h05.tkpt",
        "transcricao_24-09-26_16h05_diarizado.txt",
        f"resultados/{MID}.json",
        "audio/transcricao_24-09-26_16h05_audio.wav.enc",
        "audio/transcricao_24-09-26_16h05_mic.wav.enc",
        f"resumos/{MID}.resumo",
        f".jobs_processamento/{MID}.json",
        f".jobs_processamento/.locks/{MID}.lock",
        f"sessoes/{SESSAO}",
        f"eventos_privados/{SESSAO}",
    }
    assert not any("Reuniao_X" in c or VIZINHA in c for c in caminhos)
    assert {i.categoria for i in plano.itens} >= {"Transcrição", "Áudio", "Resumo", "Eventos do Meet"}
    assert plano.bytes_total > 0 and len(plano.plano_id) == 64


def test_exclusao_apaga_tudo_e_preserva_a_vizinha(raiz):
    antes_vizinha = {c for c in _todos(raiz) if "Reuniao_X" in c or VIZINHA in c or "99999999" in c}
    plano = ex.planejar(raiz, MID)
    ex.excluir(raiz, MID, plano.plano_id)
    depois = _todos(raiz)
    assert not any(MID in c or SESSAO in c or c.startswith("transcricao_24-09-26_16h05.") or
                   c.startswith("transcricao_24-09-26_16h05_diarizado") or c.startswith("audio/transcricao_24-09-26_16h05_audio")
                   for c in depois)
    assert antes_vizinha <= depois
    indice = json.loads((raiz / "indice.json").read_text(encoding="utf-8"))["meetings"]
    assert MID not in indice and VIZINHA in indice
    assert not (raiz / ".lixeira_exclusao").exists() or not any((raiz / ".lixeira_exclusao").iterdir())


def test_plano_desatualizado_e_recusado(raiz):
    plano = ex.planejar(raiz, MID)
    (raiz / "resumos" / f"{MID}.resumo").unlink()
    with pytest.raises(ex.PlanoDivergente):
        ex.excluir(raiz, MID, plano.plano_id)
    assert (raiz / f"transcricao_24-09-26_16h05.txt").is_file()


def test_reuniao_em_processamento_nao_pode_ser_excluida(tmp_path):
    r = tmp_path / "t"
    r.mkdir()
    _reuniao(r, MID, "transcricao_24-09-26_16h05", SESSAO, estado="processing")
    with pytest.raises(ex.ExclusaoBloqueada):
        ex.planejar(r, MID)


def test_reuniao_inexistente_e_id_malicioso(raiz):
    with pytest.raises(ex.ReuniaoNaoEncontrada):
        ex.planejar(raiz, "c" * 32)
    for ruim in ("../x", "a/b", "", "..", "x" * 100):
        with pytest.raises(ex.ReuniaoNaoEncontrada):
            ex.planejar(raiz, ruim)


def test_job_com_caminho_fora_da_raiz_e_ignorado(raiz, tmp_path):
    fora = tmp_path / "fora.wav"
    fora.write_bytes(b"x")
    job = raiz / ".jobs_processamento" / f"{MID}.json"
    dados = json.loads(job.read_text(encoding="utf-8"))
    dados["audio"] = str(fora)
    dados["mic"] = "../fora.wav"
    job.write_text(json.dumps(dados), encoding="utf-8")
    plano = ex.planejar(raiz, MID)
    ex.excluir(raiz, MID, plano.plano_id)
    assert fora.is_file()


def test_falha_no_meio_restaura_o_que_ja_tinha_movido(raiz, monkeypatch):
    plano = ex.planejar(raiz, MID)
    original = ex._mover
    chamadas = {"n": 0}

    def mover_falhando(origem, destino):
        chamadas["n"] += 1
        if chamadas["n"] == 4:
            raise OSError("disco ocupado")
        return original(origem, destino)

    monkeypatch.setattr(ex, "_mover", mover_falhando)
    with pytest.raises(OSError):
        ex.excluir(raiz, MID, plano.plano_id)
    assert {i.caminho for i in ex.planejar(raiz, MID).itens} == {i.caminho for i in plano.itens}
    assert MID in json.loads((raiz / "indice.json").read_text(encoding="utf-8"))["meetings"]
