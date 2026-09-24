# -*- coding: utf-8 -*-
"""Lista de reuniões mostra título, início real e duração (pedido do usuário, 24/09/2026).

Os metadados vêm do job (`titulo_reuniao`, `inicio_iso`, `duracao_seg`) ou, em
reuniões antigas, do nome do arquivo; nenhum conteúdo de fala é lido.
"""
from __future__ import annotations

import json
from pathlib import Path

from indice_transcricoes import listar_reunioes


def _manifesto(meeting_id: str, pasta: Path, base: str, created_at="2026-09-19T23:00:00Z") -> Path:
    from resultado_reuniao import criar_manifesto_inicial, salvar_manifesto

    resultado = pasta / f"{base}.txt"
    resultado.write_text("CANARIO fala sigilosa", encoding="utf-8")
    audio = pasta / f"{base}.wav"
    audio.write_bytes(b"\x00" * 64)
    manifesto = criar_manifesto_inicial(
        meeting_id=meeting_id, resultado=resultado, fontes_audio=[audio], raiz=pasta, created_at=created_at,
    )
    caminho = pasta / f"{base}.resultado.json"
    salvar_manifesto(caminho, manifesto)
    return caminho


def _job(pasta: Path, meeting_id: str, **metadados) -> None:
    jobs = pasta / ".jobs_processamento"
    jobs.mkdir(exist_ok=True)
    (jobs / f"{meeting_id}.json").write_text(json.dumps({"id": meeting_id, "metadados": metadados}), encoding="utf-8")


def test_titulo_inicio_e_duracao_vem_do_job(tmp_path):
    _manifesto("a" * 32, tmp_path, "transcricao_2026-09-24_16h05_planejamento")
    _job(tmp_path, "a" * 32, titulo_reuniao="Planejamento semanal", inicio_iso="2026-09-24T19:05:16Z", duracao_seg=2712.4)
    (s,), _ = listar_reunioes(tmp_path / "indice.json", cursor=None, limit=10)
    assert s.title == "Planejamento semanal"
    assert s.started_at == "2026-09-24T19:05:16Z"
    assert s.duration_ms == 2712400
    assert s.arquivo == "transcricao_2026-09-24_16h05_planejamento"


def test_reuniao_antiga_sem_job_usa_horario_do_nome(tmp_path):
    _manifesto("b" * 32, tmp_path, "transcricao_2026-09-22_13h59")
    (s,), _ = listar_reunioes(tmp_path / "indice.json", cursor=None, limit=10)
    assert s.started_at.startswith("2026-09-22T13:59")
    assert s.title is None and s.duration_ms is None


def test_lista_da_mais_recente_para_a_mais_antiga_com_cursor(tmp_path):
    datas = {"c" * 32: "2026-09-21_17h18", "d" * 32: "2026-09-24_15h54", "e" * 32: "2026-09-23_14h50"}
    for mid, data in datas.items():
        _manifesto(mid, tmp_path, f"transcricao_{data}")
    indice = tmp_path / "indice.json"
    p1, cursor = listar_reunioes(indice, cursor=None, limit=2)
    p2, fim = listar_reunioes(indice, cursor=cursor, limit=2)
    assert [s.meeting_id for s in p1 + p2] == ["d" * 32, "e" * 32, "c" * 32]
    assert fim is None


def test_job_removido_nao_apaga_titulo_ja_indexado(tmp_path):
    caminho = _manifesto("f" * 32, tmp_path, "transcricao_2026-09-24_16h05")
    _job(tmp_path, "f" * 32, titulo_reuniao="Retro", duracao_seg=60)
    listar_reunioes(tmp_path / "indice.json", cursor=None, limit=10)
    (tmp_path / ".jobs_processamento" / ("f" * 32 + ".json")).unlink()
    caminho.write_text(caminho.read_text(encoding="utf-8").replace("\n", "\n "), encoding="utf-8")  # novo sha
    (s,), _ = listar_reunioes(tmp_path / "indice.json", cursor=None, limit=10)
    assert s.title == "Retro" and s.duration_ms == 60000


def test_indice_nunca_guarda_fala(tmp_path):
    _manifesto("9" * 32, tmp_path, "transcricao_2026-09-24_16h05")
    listar_reunioes(tmp_path / "indice.json", cursor=None, limit=10)
    assert "CANARIO" not in (tmp_path / "indice.json").read_text(encoding="utf-8")


def test_ordem_compara_utc_do_job_com_hora_local_do_nome(tmp_path, monkeypatch):
    import datetime as dt

    import indice_transcricoes

    # Nome sem fuso é hora local; o job vem em UTC. 13:59 local deve vir depois de 12:00Z
    # em qualquer fuso a oeste de UTC+1 — fixamos UTC-3 para o teste ser determinístico.
    fuso = dt.timezone(dt.timedelta(hours=-3))
    original = indice_transcricoes._instante

    def em_utc_menos_3(iso):
        texto = str(iso)
        if texto and not texto.endswith("Z") and "+" not in texto[10:]:
            return dt.datetime.fromisoformat(texto).replace(tzinfo=fuso).timestamp()
        return original(iso)

    monkeypatch.setattr(indice_transcricoes, "_instante", em_utc_menos_3)
    _manifesto("1" * 32, tmp_path, "transcricao_2026-09-22_13h59")  # 16:59Z
    _manifesto("2" * 32, tmp_path, "transcricao_2026-09-22_15h00")
    _job(tmp_path, "2" * 32, inicio_iso="2026-09-22T15:00:00Z")  # 12:00 local
    pagina, _ = listar_reunioes(tmp_path / "indice.json", cursor=None, limit=10)
    assert [s.meeting_id for s in pagina] == ["1" * 32, "2" * 32]
