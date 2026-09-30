# -*- coding: utf-8 -*-
"""T-15.D2 / SEC-15.D2 — OpenRouter por escolha: chave cifrada, consentimento, marca, sem fallback.

Nenhum teste acessa a rede: `urllib.request.urlopen` é substituído.
"""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

import config_user
import provedor_openrouter as po
from provedores_ia import ErroProvedor, ProvedorOllama, provedor_para

CHAVE = "sk-or-v1-segredo-sintetico-123456"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _abrir(respostas, pedidos):
    def abrir(req, timeout=None):
        pedidos.append(req)
        resposta = respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return _Resp(resposta if isinstance(resposta, bytes) else json.dumps(resposta).encode())
    return abrir


def _http(codigo):
    return urllib.error.HTTPError("https://openrouter.ai/api/v1/x", codigo, "erro", {}, None)


def test_chave_cifrada_dpapi(tmp_path):
    po.salvar_chave(CHAVE)
    bruto = Path(config_user.CONFIG_USER_FILE).read_text(encoding="utf-8")
    assert CHAVE not in bruto and "openrouter_chave_dpapi" in bruto
    assert po.chave() == CHAVE
    assert po.chave_final() == "3456"


def test_sem_consentimento_recusa():
    po.salvar_chave(CHAVE)
    config_user.atualizar(ia_resumo_provedor="openrouter")
    with pytest.raises(ErroProvedor) as erro:
        provedor_para("resumo")
    assert erro.value.codigo == "sem_consentimento"
    po.consentir()
    assert provedor_para("resumo").id == "openrouter"


def test_sem_chave_erro_explicito():
    config_user.atualizar(ia_chat_provedor="openrouter")
    po.consentir()
    with pytest.raises(ErroProvedor) as erro:
        provedor_para("chat")
    assert erro.value.codigo == "sem_chave"


def test_padrao_e_ollama():
    assert isinstance(provedor_para("resumo"), ProvedorOllama)


def test_corpo_nega_coleta_e_nao_leva_opcoes_do_ollama(monkeypatch):
    pedidos = []
    monkeypatch.setattr("urllib.request.urlopen",
                        _abrir([{"choices": [{"message": {"content": "resumo remoto"}}]}], pedidos))
    texto = po.ProvedorOpenRouter(CHAVE).conversar([{"role": "user", "content": "x"}], modelo="org/modelo",
                                                    opcoes={"temperature": 0.2, "num_ctx": 8192}, pensar=False)
    assert texto == "resumo remoto"
    corpo = json.loads(pedidos[0].data)
    assert corpo["provider"] == {"data_collection": "deny", "zdr": True}
    assert corpo["temperature"] == 0.2 and "num_ctx" not in json.dumps(corpo) and "options" not in corpo
    assert pedidos[0].full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert pedidos[0].get_header("Authorization") == f"Bearer {CHAVE}"
    assert pedidos[0].get_header("X-openrouter-title") == "Transkriptor"


def test_chave_invalida_erro_explicito_e_sem_chave_na_mensagem(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _abrir([_http(401), _http(401)], []))
    provedor = po.ProvedorOpenRouter(CHAVE)
    assert provedor.estado().estado == "chave_invalida"
    with pytest.raises(ErroProvedor) as erro:
        provedor.conversar([{"role": "user", "content": "segredo da reunião"}], modelo="m")
    assert erro.value.codigo == "chave_invalida"
    assert CHAVE not in str(erro.value) and "segredo" not in str(erro.value)


def test_chave_nunca_em_log():
    from status_seguro import _sem_credencial

    assert CHAVE not in _sem_credencial(f"falhou com a chave {CHAVE} agora")


def test_sse_normalizado(monkeypatch):
    linhas = (b': OPENROUTER PROCESSING\n\n'
              b'data: {"choices":[{"delta":{"content":"Ol"}}]}\n\n'
              b'data: {"choices":[{"delta":{"content":"\xc3\xa1"}}]}\n\n'
              b'data: [DONE]\n\n')
    pedidos = []
    monkeypatch.setattr("urllib.request.urlopen", _abrir([linhas], pedidos))
    pedacos = list(po.ProvedorOpenRouter(CHAVE).conversar_stream([{"role": "user", "content": "x"}], modelo="m"))
    assert "".join(pedacos) == "Olá"
    assert json.loads(pedidos[0].data)["stream"] is True


def test_modelos_e_contexto(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _abrir([{"data": [
        {"id": "org/a", "name": "A", "context_length": 128000}, {"id": "org/b", "name": "B"}]}], []))
    provedor = po.ProvedorOpenRouter(CHAVE)
    modelos = provedor.listar_modelos()
    assert [(m.id, m.contexto, m.local) for m in modelos] == [("org/a", 128000, False), ("org/b", None, False)]
    assert provedor.contexto("org/a") == 128000


def test_sem_fallback_silencioso(monkeypatch):
    """OpenRouter escolhido e fora do ar: erro visível, nenhuma chamada ao Ollama."""
    import assistente_ollama

    po.salvar_chave(CHAVE)
    po.consentir()
    config_user.atualizar(ia_chat_provedor="openrouter")
    pedidos = []
    monkeypatch.setattr("urllib.request.urlopen", _abrir([OSError("sem rede")], pedidos))
    texto = assistente_ollama.chamar_ollama_sync("org/m", [{"role": "user", "content": "q"}])
    assert texto.startswith("[") and "OpenRouter" in texto
    assert all("openrouter.ai" in p.full_url for p in pedidos)


def test_marca_provedor_no_resumo(monkeypatch):
    import central_resumos

    po.salvar_chave(CHAVE)
    po.consentir()
    config_user.atualizar(ia_resumo_provedor="openrouter", ia_resumo_modelo="org/resumidor")
    assert central_resumos._modelos_instalados() == ["org/resumidor"]
    assert central_resumos._marca("org/resumidor") == "\n\n_Gerado por OpenRouter · org/resumidor_"
    config_user.atualizar(ia_resumo_provedor="ollama")
    assert central_resumos._marca("granite4.1:3b") == ""


def test_servico_acrescenta_a_marca_uma_vez(tmp_path):
    from resumo_reuniao import ServicoResumos

    chamadas = []

    def chamar(modelo, mensagens):
        chamadas.append(modelo)
        return "Resumo sintético."

    s = ServicoResumos(tmp_path, carregar=lambda mid: {"revision": "r1", "segmentos": [
        {"segment_id": "s", "start_ms": 0, "end_ms": 1000, "audio_source": "loopback", "text": "bom dia",
         "speaker_cluster_id": "FALANTE_00"}], "mapeamento": {}},
        chamar=chamar, modelos=lambda: ["org/m"], ocupado=lambda: False, orcamento=lambda m: 10000,
        elegivel=lambda mid: True, marca=lambda m: f" [{m}]")
    s._processar("r")
    assert s.obter("r")["resumo"].endswith("Resumo sintético. [org/m]")
