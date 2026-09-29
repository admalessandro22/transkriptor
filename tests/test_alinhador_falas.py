# -*- coding: utf-8 -*-
"""T-15.C2 / FR-15.C2 — alinhamento legenda↔Whisper e corte por troca de falante.

Reuniões 100% sintéticas: tokens inventados, tempos controlados. A legenda
chega `atraso_ms` depois da fala (latência do ASR do Google) e erra 10% das
palavras; os segmentos do Whisper atravessam trocas de falante de propósito.
"""
from __future__ import annotations

import random

import pytest

from alinhador_falas import alinhar_segmentos, atribuir_palavras, estimar_atraso
from audio_fontes import AudioSource, PalavraSTT, SegmentoSTT
from linha_tempo_falas import construir_linha_tempo

NOMES = {"dev-1": "Ana", "dev-2": "Bruno", "dev-3": "Carla", "dev-4": "Davi"}
_SILABAS = ["ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "zo"]
VOCAB = [a + b + c for a in _SILABAS for b in _SILABAS for c in ("", "s", "r")]
# Palavras funcionais do português: repetem-se o tempo todo e confundem âncoras.
COMUNS = ("o a de que e do da em um para com não uma os no se na por mais as dos como mas "
          "foi ao ele das tem seu sua ou ser quando muito há nos já está eu também só isso").split()


def reuniao_sintetica(seed, minutos, *, atraso_ms=900, deriva_ms=0, seg_ms=6000,
                      erro_legenda=0.1, texto_legenda=True, comuns=0.0, jitter_ms=80,
                      interrupcoes=0.0):
    rnd = random.Random(seed)

    def sortear():
        return rnd.choice(COMUNS) if comuns and rnd.random() < comuns else rnd.choice(VOCAB)

    total = int(minutos * 60_000)
    palavras, eventos, t, turno = [], [], 500, 0
    while t < total:
        anterior = palavras[-1][3] if palavras else None
        pid = rnd.choice([p for p in NOMES if p != anterior])
        n = rnd.randint(1, 3) if rnd.random() < 0.15 else rnd.randint(4, 14)
        if interrupcoes and palavras and rnd.random() < interrupcoes:  # começa antes de o outro terminar
            t = max(palavras[-1][1] + 100, t - rnd.randint(200, 600))
        ini_turno, toks = t, []
        for _ in range(n):
            dur = rnd.randint(220, 450)
            tok = sortear()
            palavras.append((tok, t, t + dur, pid))
            toks.append(tok)
            t += dur + rnd.randint(20, 120)
        fim_turno = palavras[-1][2]
        atraso = atraso_ms + deriva_ms * (ini_turno / total)
        if texto_legenda:
            texto = " ".join(tok if rnd.random() > erro_legenda else sortear() for tok in toks)
        else:
            texto = " ".join(f"outra{rnd.randint(0, 9999)}" for _ in toks)
        eventos.append({
            "kind": "caption", "caption_id": f"rtc-{turno}/{pid}", "caption_revision": 2,
            "participant_id": pid, "display_name": NOMES[pid], "text": texto,
            "event_id": f"e-{turno}",
            "ts_sec": (ini_turno + atraso + rnd.randint(-jitter_ms, jitter_ms)) / 1000,
            "ts_fim_sec": (fim_turno + atraso + rnd.randint(-jitter_ms, jitter_ms)) / 1000,
        })
        turno += 1
        t += rnd.randint(150, 900)
    ordem = sorted(range(len(palavras)), key=lambda i: palavras[i][1])
    palavras = [palavras[i] for i in ordem]
    segmentos, atual = [], []

    def fechar():
        if atual:
            segmentos.append(SegmentoSTT(
                f"loopback-0-{len(segmentos)}", atual[0][1], atual[-1][2], AudioSource.LOOPBACK,
                " ".join(w[0] for w in atual), False,
                tuple(PalavraSTT(w[0], w[1], w[2], 0.9) for w in atual)))
            atual.clear()

    for palavra in palavras:
        if atual and palavra[2] - atual[0][1] > seg_ms:
            fechar()
        atual.append(palavra)
    fechar()
    return segmentos, eventos, [w[3] for w in palavras]


def _todas_palavras(segmentos):
    return [p for s in segmentos for p in s.words]


def _acerto_por_palavra(segmentos, eventos, verdade):
    palavras = _todas_palavras(segmentos)
    falas = construir_linha_tempo(eventos)
    alinhamento = estimar_atraso(palavras, falas)
    atribuidas = atribuir_palavras(palavras, falas, alinhamento)
    certas = sum(1 for a, v in zip(atribuidas, verdade) if a.participant_id == v)
    return certas / len(verdade), alinhamento


def test_recupera_atraso_simulado():
    segmentos, eventos, _ = reuniao_sintetica(1, 3, atraso_ms=1200)
    alinhamento = estimar_atraso(_todas_palavras(segmentos), construir_linha_tempo(eventos))
    assert alinhamento.estimado is True
    assert alinhamento.atraso_global_ms == pytest.approx(-1200, abs=50)
    assert alinhamento.concordancia > 0.5


def test_deriva_linear_refinada():
    segmentos, eventos, verdade = reuniao_sintetica(2, 10, atraso_ms=800, deriva_ms=400)
    acerto, alinhamento = _acerto_por_palavra(segmentos, eventos, verdade)
    assert len(alinhamento.atrasos_janela) >= 5
    assert alinhamento.atrasos_janela[max(alinhamento.atrasos_janela)] < alinhamento.atrasos_janela[0] - 150
    assert acerto >= 0.98


def test_aceite_dez_minutos_quatro_falantes():
    """Aceite da task: atraso −900 ms, deriva 200 ms, ≥ 98% das palavras certas."""
    segmentos, eventos, verdade = reuniao_sintetica(3, 10, atraso_ms=900, deriva_ms=200)
    acerto, _ = _acerto_por_palavra(segmentos, eventos, verdade)
    assert acerto >= 0.98


def test_segmento_com_duas_vozes_e_cortado():
    ana = [PalavraSTT(t, i * 400, i * 400 + 350, 0.9) for i, t in enumerate(["bafo", "cedi", "lame", "nipo"])]
    bruno = [PalavraSTT(t, 2000 + i * 400, 2000 + i * 400 + 350, 0.9)
             for i, t in enumerate(["ruza", "tevi", "zoba", "gula"])]
    seg = SegmentoSTT("loopback-0-0", 0, 3550, AudioSource.LOOPBACK,
                      "bafo cedi lame nipo ruza tevi zoba gula", False, tuple(ana + bruno))
    eventos = [
        {"kind": "caption", "caption_id": "rtc-1/dev-1", "caption_revision": 1, "participant_id": "dev-1",
         "display_name": "Ana", "text": "bafo cedi lame nipo", "event_id": "a", "ts_sec": 0.9, "ts_fim_sec": 2.45},
        {"kind": "caption", "caption_id": "rtc-2/dev-2", "caption_revision": 1, "participant_id": "dev-2",
         "display_name": "Bruno", "text": "ruza tevi zoba gula", "event_id": "b", "ts_sec": 2.9, "ts_fim_sec": 4.45},
    ]
    resultado = alinhar_segmentos([seg], eventos, incerteza_ms=10)
    cortes = resultado.fundidos
    assert [c.text for c in cortes] == ["bafo cedi lame nipo", "ruza tevi zoba gula"]
    assert cortes[0].start_ms == 0 and cortes[-1].end_ms == 3550
    assert cortes[1].start_ms == 2000
    nomes = [resultado.atribuicoes[c.segment_id].display_name for c in cortes]
    assert nomes == ["Ana", "Bruno"]
    assert all(resultado.atribuicoes[c.segment_id].source == "meet_alinhamento" for c in cortes)


def test_frase_curta_atribuida_por_tempo():
    """Um "sim" de 0,4 s entre falas longas vai para quem disse, sem virar fragmento solto."""
    segmentos, eventos, verdade = reuniao_sintetica(4, 4)
    palavras = _todas_palavras(segmentos)
    falas = construir_linha_tempo(eventos)
    atribuidas = atribuir_palavras(palavras, falas, estimar_atraso(palavras, falas))
    curtas = [i for i, e in enumerate(eventos) if len(e["text"].split()) == 1]
    assert curtas, "a reunião sintética precisa de falas de uma palavra"
    inicio_por_fala = {}
    k = 0
    for idx, ev in enumerate(eventos):
        inicio_por_fala[idx] = k
        k += len(ev["text"].split())
    for idx in curtas:
        i = inicio_por_fala[idx]
        assert atribuidas[i].participant_id == verdade[i]


def test_sobreposicao_sem_desempate_marca_overlap():
    palavras = (PalavraSTT("sim", 1000, 1300, 0.9), PalavraSTT("sim", 1300, 1600, 0.9))
    seg = SegmentoSTT("loopback-0-0", 1000, 1600, AudioSource.LOOPBACK, "sim sim", False, palavras)
    eventos = [
        {"kind": "caption", "caption_id": f"rtc-{i}/{pid}", "caption_revision": 1, "participant_id": pid,
         "display_name": NOMES[pid], "text": "sim", "event_id": pid, "ts_sec": 1.9, "ts_fim_sec": 2.6}
        for i, pid in enumerate(("dev-1", "dev-2"))
    ]
    resultado = alinhar_segmentos([seg], eventos, incerteza_ms=10)
    assert resultado.fundidos[0].overlap is True
    assert resultado.atribuicoes[resultado.fundidos[0].segment_id].status.value == "conflict"


def test_concordancia_baixa_reduz_confianca():
    """Legenda em outro idioma: sem âncora de texto, só o tempo — com confiança menor."""
    seg_ok, ev_ok, _ = reuniao_sintetica(5, 3, atraso_ms=1000)
    seg_ruim, ev_ruim, _ = reuniao_sintetica(5, 3, atraso_ms=1000, texto_legenda=False)
    bom = alinhar_segmentos(seg_ok, ev_ok, incerteza_ms=10)
    ruim = alinhar_segmentos(seg_ruim, ev_ruim, incerteza_ms=10)
    assert ruim.alinhamento["estimado"] is False
    assert ruim.alinhamento["concordancia"] < bom.alinhamento["concordancia"]

    def confianca_media(r):
        valores = [a.score for a in r.atribuicoes.values() if a.score is not None]
        return sum(valores) / len(valores)

    assert confianca_media(ruim) < confianca_media(bom)
    assert any(a.display_name for a in ruim.atribuicoes.values())


def test_sem_linha_do_tempo_nao_altera():
    segmentos, eventos, _ = reuniao_sintetica(6, 1)
    for ev in eventos:
        del ev["ts_sec"], ev["ts_fim_sec"]
    resultado = alinhar_segmentos(segmentos, eventos, incerteza_ms=10)
    assert resultado.fundidos == list(segmentos)
    assert resultado.atribuicoes == {}
    assert resultado.alinhamento is None


def test_relogio_incerto_nao_alinha():
    segmentos, eventos, _ = reuniao_sintetica(7, 1)
    resultado = alinhar_segmentos(segmentos, eventos, incerteza_ms=5000)
    assert resultado.fundidos == list(segmentos) and resultado.atribuicoes == {}


def test_segmentos_cortados_mantem_nome_certo():
    segmentos, eventos, verdade = reuniao_sintetica(8, 5)
    resultado = alinhar_segmentos(segmentos, eventos, incerteza_ms=10)
    certos = total = 0
    por_token_tempo = {(p.w, p.ini_ms): v for p, v in zip(_todas_palavras(segmentos), verdade)}
    for seg in resultado.fundidos:
        nome = resultado.atribuicoes[seg.segment_id].display_name
        for p in seg.words:
            total += 1
            certos += nome == NOMES[por_token_tempo[(p.w, p.ini_ms)]]
    assert certos / total >= 0.95
    assert len(resultado.fundidos) > len(segmentos)


def test_diagnostico_sem_conteudo():
    segmentos, eventos, _ = reuniao_sintetica(9, 2)
    resultado = alinhar_segmentos(segmentos, eventos, incerteza_ms=10)
    texto = repr(resultado.alinhamento)
    assert not any(ev["text"].split()[0] in texto for ev in eventos)
    assert not any(nome in texto for nome in NOMES.values())


def test_ruido_realista_mantem_acerto():
    """Palavras funcionais, 30% de erro na legenda, ±300 ms e interrupções."""
    segmentos, eventos, verdade = reuniao_sintetica(
        101, 10, atraso_ms=1200, deriva_ms=300, erro_legenda=0.3, comuns=0.55,
        jitter_ms=300, interrupcoes=0.25)
    acerto, alinhamento = _acerto_por_palavra(segmentos, eventos, verdade)
    assert alinhamento.estimado is True
    assert acerto >= 0.97


def test_combinar_manual_prevalece_e_desconhecido_nao_apaga_texto():
    from alinhador_falas import combinar_atribuicoes
    from identidade_reuniao import AssignmentStatus, Atribuicao

    def atr(status, nome):
        return Atribuicao("dev-9", nome, "meet_alinhamento", 0.9, ("e",), status, "v")

    por_texto = {
        "manual": {"status": "confirmed", "display_name": "Carla", "source": "manual"},
        "texto": {"status": "suggested", "display_name": "Davi", "source": "caption"},
        "troca": {"status": "suggested", "display_name": "Davi", "source": "caption"},
    }
    combinado = combinar_atribuicoes(por_texto, {
        "manual": atr(AssignmentStatus.SUGGESTED, "Bruno"),
        "texto": atr(AssignmentStatus.UNKNOWN, None),
        "troca": atr(AssignmentStatus.CONFLICT, None),
        "novo": atr(AssignmentStatus.SUGGESTED, "Ana"),
    })
    assert combinado["manual"]["display_name"] == "Carla"
    assert combinado["texto"]["display_name"] == "Davi"
    assert combinado["troca"]["status"] == "conflict"
    assert combinado["novo"]["display_name"] == "Ana"
