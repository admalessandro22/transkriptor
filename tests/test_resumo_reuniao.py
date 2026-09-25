# -*- coding: utf-8 -*-
"""Resumo curto por reunião com a IA local (pedido do usuário, 24/09/2026)."""
from __future__ import annotations

import threading
import time

import pytest

import resumo_reuniao as rr


def _dados(revision="rev-1"):
    return {
        "revision": revision,
        "segmentos": [
            {"speaker_cluster_id": "FALANTE_00", "start_ms": 0, "text": "Vamos fechar o cronograma.",
             "assignment": {"status": "confirmed", "display_name": "Ana Fictícia"}},
            {"speaker_cluster_id": "FALANTE_01", "start_ms": 65000, "text": "Entrego o relatório na sexta."},
        ],
        "mapeamento": {"FALANTE_01": {"display_name": "Bruno Fictício"}},
    }


def test_texto_da_reuniao_tem_nome_e_horario():
    texto = rr.texto_da_reuniao(_dados())
    assert "[00:00] Ana Fictícia: Vamos fechar o cronograma." in texto
    assert "[01:05] Bruno Fictício: Entrego o relatório na sexta." in texto


def test_limite_de_500_caracteres_corta_em_frase():
    longo = ("Frase completa número um. " * 40).strip()
    curto = rr.limitar_resumo(longo)
    assert len(curto) <= 500
    assert curto.endswith(".")
    assert rr.limitar_resumo("  Resumo\n com   espaços.  ") == "Resumo com espaços."
    sem_ponto = "palavra " * 100
    assert len(rr.limitar_resumo(sem_ponto)) <= 500 and rr.limitar_resumo(sem_ponto).endswith("…")


def test_gerar_resumo_pede_ate_500_caracteres_em_portugues():
    pedidos = []

    def chamar(modelo, mensagens):
        pedidos.append((modelo, mensagens))
        return "Ana e Bruno fecharam o cronograma; relatório sai sexta."

    resumo = rr.gerar_resumo(_dados(), "modelo-x", chamar, orcamento_chars=10000)
    assert resumo == "Ana e Bruno fecharam o cronograma; relatório sai sexta."
    sistema = pedidos[0][1][0]["content"]
    assert "500 caracteres" in sistema and "português" in sistema


def test_erro_do_ollama_nao_vira_resumo():
    with pytest.raises(rr.ResumoIndisponivel):
        rr.gerar_resumo(_dados(), "m", lambda m, msgs: "[Erro ao contatar o Ollama: recusado]", orcamento_chars=10000)
    with pytest.raises(rr.ResumoIndisponivel):
        rr.gerar_resumo({"segmentos": []}, "m", lambda m, msgs: "x", orcamento_chars=10000)


def test_escolhe_modelo_preferido_instalado():
    # granite4.1 primeiro: resumo equivalente e bem mais rápido (decisão do usuário, 24/09/2026)
    assert rr.escolher_modelo(["ornith:latest", "granite4.1:3b", "gemma4:latest"]) == "granite4.1:3b"
    assert rr.escolher_modelo(["ornith:latest", "gemma4:latest"]) == "gemma4:latest"
    assert rr.escolher_modelo(["ornith:latest"]) == "ornith:latest"
    assert rr.escolher_modelo([]) is None


class _Servico:
    def __init__(self, tmp_path, *, ocupado=lambda: False, resposta="Resumo curto.", elegivel=lambda mid: True):
        self.chamadas = 0
        self.dados = _dados()

        def chamar(modelo, mensagens):
            self.chamadas += 1
            return resposta

        self.servico = rr.ServicoResumos(
            tmp_path / "resumos",
            carregar=lambda mid: self.dados if mid == "reuniao-1" else None,
            chamar=chamar,
            modelos=lambda: ["gemma4:latest"],
            ocupado=ocupado,
            orcamento=lambda modelo: 10000,
            espera_ocupado_seg=0.05,
            elegivel=elegivel,
        )
        self.servico._espera_retry_seg = 0.05


def _esperar(servico, mid, estado, limite=5.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        r = servico.obter(mid)
        if r["estado"] == estado:
            return r
        time.sleep(0.02)
    raise AssertionError(f"estado {estado!r} não alcançado: {servico.obter(mid)}")


def test_servico_gera_uma_vez_guarda_cifrado_e_reaproveita(tmp_path, chave_teste):
    s = _Servico(tmp_path)
    assert s.servico.obter("reuniao-1")["estado"] == "gerando"
    r = _esperar(s.servico, "reuniao-1", "pronto")
    assert r["resumo"] == "Resumo curto."
    arquivos = list((tmp_path / "resumos").iterdir())
    assert len(arquivos) == 1 and b"Resumo curto" not in arquivos[0].read_bytes()
    novo = _Servico(tmp_path)  # outro processo: lê do disco, não chama a IA
    assert novo.servico.obter("reuniao-1") == {"estado": "pronto", "resumo": "Resumo curto."}
    assert novo.chamadas == 0
    s.servico.parar()


def test_correcao_de_nome_refaz_o_resumo(tmp_path, chave_teste):
    s = _Servico(tmp_path)
    s.servico.obter("reuniao-1")
    _esperar(s.servico, "reuniao-1", "pronto")
    s.dados = _dados(revision="rev-2")
    assert s.servico.obter("reuniao-1")["estado"] == "gerando"
    _esperar(s.servico, "reuniao-1", "pronto")
    assert s.chamadas == 2
    s.servico.parar()


def test_nao_gera_enquanto_o_app_grava(tmp_path, chave_teste):
    gravando = threading.Event()
    gravando.set()
    s = _Servico(tmp_path, ocupado=gravando.is_set)
    s.servico.obter("reuniao-1")
    time.sleep(0.3)
    assert s.chamadas == 0 and s.servico.obter("reuniao-1")["estado"] == "gerando"
    gravando.clear()
    _esperar(s.servico, "reuniao-1", "pronto")
    s.servico.parar()


def test_reuniao_inexistente_e_ia_fora_do_ar(tmp_path, chave_teste):
    s = _Servico(tmp_path, resposta="[Erro ao contatar o Ollama: offline]")
    assert s.servico.obter("nao-existe")["estado"] == "indisponivel"
    s.servico.obter("reuniao-1")
    r = _esperar(s.servico, "reuniao-1", "indisponivel")
    assert "IA local" in r["motivo"]
    s.servico.parar()


def test_parar_interrompe_espera_por_app_ocupado(tmp_path, chave_teste):
    entrou = threading.Event()
    servico = rr.ServicoResumos(
        tmp_path / "resumos", carregar=lambda mid: _dados(),
        chamar=lambda modelo, mensagens: "Nunca chamado.",
        modelos=lambda: ["granite4.1:3b"],
        ocupado=lambda: entrou.set() or True,
        espera_ocupado_seg=10,
    )
    servico.obter("reuniao-1")
    assert entrou.wait(1)

    servico.parar()

    assert not servico._thread.is_alive()


def test_falha_transitoria_da_ia_tenta_de_novo_automaticamente(tmp_path, chave_teste):
    respostas = iter(["[Erro ao contatar o Ollama: HTTPError]", "Resumo recuperado."])
    chamadas = []
    servico = rr.ServicoResumos(
        tmp_path / "resumos", carregar=lambda mid: _dados(),
        chamar=lambda modelo, mensagens: chamadas.append(modelo) or next(respostas),
        modelos=lambda: ["granite4.1:3b"], orcamento=lambda modelo: 10000,
        espera_ocupado_seg=0.01,
    )
    servico._espera_retry_seg = 0.01

    assert servico.obter("reuniao-1")["estado"] == "gerando"
    pronto = _esperar(servico, "reuniao-1", "pronto")

    assert pronto["resumo"] == "Resumo recuperado."
    assert len(chamadas) == 2
    servico.parar()


def test_rota_da_central_devolve_estado_sem_expor_fala(tmp_path, monkeypatch, headers_token, chave_teste):
    import central_resumos
    from assistente import app
    from resultado_edicao import SegmentoResultado, salvar_segmentos

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "resultados").mkdir()
    salvar_segmentos(tmp_path / "resultados" / "reuniao-x.json",
                     [SegmentoResultado("s1", 0, 1000, "loopback", "fala sigilosa", "FALANTE_00")], {})
    monkeypatch.setattr(central_resumos, "_servico", None)
    monkeypatch.setattr(central_resumos, "_modelos_instalados", lambda: ["gemma4:latest"])
    monkeypatch.setattr(central_resumos, "_orcamento", lambda m: 10000)
    monkeypatch.setattr(central_resumos, "_chamar_resumo", lambda m, msgs: "Resumo sintético.")
    monkeypatch.setattr(central_resumos, "_elegivel", lambda raiz, mid: False)
    cliente = app.test_client()
    try:
        assert cliente.get("/api/reunioes/reuniao-x/resumo", headers=headers_token).get_json() == {"estado": "sem_resumo"}
        primeira = cliente.get("/api/reunioes/reuniao-x/resumo?gerar=1", headers=headers_token).get_json()
        assert primeira["estado"] in ("gerando", "pronto")
        fim = time.monotonic() + 5
        while time.monotonic() < fim:
            r = cliente.get("/api/reunioes/reuniao-x/resumo", headers=headers_token)
            if r.get_json()["estado"] == "pronto":
                break
            time.sleep(0.05)
        assert r.get_json() == {"estado": "pronto", "resumo": "Resumo sintético."}
        assert "sigilosa" not in r.get_data(as_text=True)
        assert cliente.get("/api/reunioes/nao-existe/resumo", headers=headers_token).get_json()["estado"] == "indisponivel"
    finally:
        central_resumos.servico().parar()
        monkeypatch.setattr(central_resumos, "_servico", None)


def test_chamada_do_resumo_desliga_raciocinio_e_fixa_contexto(monkeypatch):
    import json as _json

    import central_resumos

    enviados = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps({"message": {"content": "ok"}}).encode()

    def abrir(req, timeout):
        enviados.append((_json.loads(req.data), timeout))
        return _Resp()

    monkeypatch.setattr(central_resumos.urllib.request, "urlopen", abrir)
    monkeypatch.setattr(central_resumos, "_contexto", lambda m: 8192)
    assert central_resumos._chamar_resumo("gemma4:latest", [{"role": "user", "content": "x"}]) == "ok"
    corpo, timeout = enviados[0]
    assert corpo["think"] is False and corpo["options"]["num_ctx"] == 8192
    assert timeout == central_resumos.TIMEOUT_RESUMO_SEG


@pytest.mark.parametrize("estado,processamento,ocupado", [
    ("aguardando", None, False),
    ("aguardando", "Pronta", False),      # regressão: "Pronta" fica no campo após processar
    ("aguardando", "Falhou", False),
    ("aguardando", "Cancelada", False),
    ("aguardando", "Processando", True),
    ("aguardando", "Em fila", True),
    ("gravando", None, True),
    ("separando_vozes", None, True),
])
def test_app_ocupado_so_quando_grava_ou_processa(monkeypatch, estado, processamento, ocupado):
    from types import SimpleNamespace

    import app_estado_ui
    import central_resumos

    monkeypatch.setattr(app_estado_ui, "provedor_atual", lambda: (lambda: SimpleNamespace(estado=estado, processamento=processamento)))
    assert central_resumos._app_ocupado() is ocupado


def test_reuniao_antiga_nao_entra_na_fila_mas_pode_ser_gerada_a_pedido(tmp_path, chave_teste):
    s = _Servico(tmp_path, elegivel=lambda mid: False)
    assert s.servico.obter("reuniao-1") == {"estado": "sem_resumo"}
    time.sleep(0.2)
    assert s.chamadas == 0
    assert s.servico.obter("reuniao-1", gerar=True)["estado"] == "gerando"
    r = _esperar(s.servico, "reuniao-1", "pronto")
    assert r["resumo"] == "Resumo curto." and s.chamadas == 1
    s.servico.parar()


def test_resumo_ja_existente_de_reuniao_antiga_continua_visivel(tmp_path, chave_teste):
    s = _Servico(tmp_path)
    s.servico.obter("reuniao-1")
    _esperar(s.servico, "reuniao-1", "pronto")
    s.servico.parar()
    antiga = _Servico(tmp_path, elegivel=lambda mid: False)
    assert antiga.servico.obter("reuniao-1") == {"estado": "pronto", "resumo": "Resumo curto."}


def test_elegivel_so_reunioes_que_comecam_depois_do_corte(tmp_path, monkeypatch):
    import json as _json

    import central_resumos

    raiz = tmp_path
    (raiz / "indice.json").write_text(_json.dumps({"version": 1, "meetings": {
        "nova": {"started_at": "2026-09-24T22:00:00Z"},
        "antiga": {"started_at": "2026-09-24T16:05:00"},
        "sem_data": {},
    }}), encoding="utf-8")
    monkeypatch.setattr(central_resumos, "RESUMOS_AUTOMATICOS_DESDE", "2026-09-24T18:40:00-03:00")
    assert central_resumos._elegivel(raiz, "nova") is True
    assert central_resumos._elegivel(raiz, "antiga") is False
    assert central_resumos._elegivel(raiz, "sem_data") is False
    assert central_resumos._elegivel(raiz, "inexistente") is False


def test_agendar_job_concluido_usa_data_do_job_sem_depender_do_indice(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import central_resumos

    servico = MagicMock()
    monkeypatch.setattr(central_resumos, "servico", lambda: servico)
    nova = SimpleNamespace(
        id="nova", estado="ready",
        metadados={"inicio_iso": "2026-09-24T19:22:46-03:00"},
    )
    antiga = SimpleNamespace(
        id="antiga", estado="ready",
        metadados={"inicio_iso": "2026-09-24T16:05:00-03:00"},
    )
    sem_data = SimpleNamespace(id="sem-data", estado="ready", metadados={})

    for job in (nova, antiga, sem_data):
        central_resumos.agendar_concluida(job)

    servico.obter.assert_called_once_with("nova", gerar=True)


def test_resumo_em_background_respeita_worker_sem_central_aberta(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import app_estado_ui
    import central_resumos
    from app_processamento import ProcessamentoReuniaoMixin

    app_estado_ui.registrar_provedor(None)
    app = ProcessamentoReuniaoMixin.__new__(ProcessamentoReuniaoMixin)
    app._estado_processamento = None
    app._lock = threading.Lock()
    app._atualizar_tooltip = lambda: None
    app.fila = MagicMock()
    app.fila.recuperar_interrompidos.return_value = 0
    app.fila.listar.return_value = [
        SimpleNamespace(id="pendente", estado="pending", atualizado_em="2026-09-25T01:00:00Z")
    ]
    app._despachar_proximo_job = lambda: setattr(app, "_estado_processamento", "Processando")
    monkeypatch.setattr(
        app_estado_ui, "snapshot",
        lambda atual: SimpleNamespace(estado="aguardando", processamento=atual._estado_processamento),
    )
    try:
        app._preparar_processamento()
        assert central_resumos._app_ocupado() is True
    finally:
        app_estado_ui.registrar_provedor(None)
