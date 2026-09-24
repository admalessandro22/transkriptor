"""Origem, host e formato das mutações HTTP locais."""
import pytest

from assistente import COOKIE_TOKEN, HEADER_TOKEN, app, obter_token_sessao


@pytest.mark.parametrize("rota", ["correcao", "desfazer", "exportar-txt"])
def test_cookie_nao_autoriza_origem_de_outra_porta(rota):
    client = app.test_client()
    client.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    resposta = client.post(
        f"/api/reunioes/inexistente/{rota}",
        headers={"Origin": "http://localhost:9999"},
        json={"expected_revision": "rev-1"},
    )
    assert resposta.status_code == 403


@pytest.mark.parametrize("rota", ["correcao", "desfazer", "exportar-txt", "chat"])
def test_cookie_sem_origin_nao_autoriza_mutacao(rota):
    client = app.test_client()
    client.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    caminho = f"/api/reunioes/inexistente/{rota}" if rota != "chat" else "/api/chat"
    resposta = client.post(caminho, json={"expected_revision": "rev-1"})
    assert resposta.status_code == 403


@pytest.mark.parametrize("rota", ["correcao", "desfazer", "exportar-txt", "chat"])
def test_header_secreto_sem_origin_passa_pelo_guard(rota):
    client = app.test_client()
    caminho = f"/api/reunioes/inexistente/{rota}" if rota != "chat" else "/api/chat"
    resposta = client.post(
        caminho, json={"expected_revision": "rev-1"},
        headers={HEADER_TOKEN: obter_token_sessao()},
    )
    assert resposta.status_code not in (403, 415)


@pytest.mark.parametrize("rota", ["correcao", "desfazer", "exportar-txt", "chat"])
def test_mutacao_exige_json(rota):
    client = app.test_client()
    caminho = f"/api/reunioes/inexistente/{rota}" if rota != "chat" else "/api/chat"
    resposta = client.post(caminho, data="x", headers={HEADER_TOKEN: obter_token_sessao()})
    assert resposta.status_code == 415


@pytest.mark.parametrize("rota", ["correcao", "desfazer", "exportar-txt", "chat"])
def test_cookie_com_origin_exata_passa_pelo_guard(rota):
    client = app.test_client()
    client.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    caminho = f"/api/reunioes/inexistente/{rota}" if rota != "chat" else "/api/chat"
    resposta = client.post(caminho, json={"expected_revision": "rev-1"}, headers={"Origin": "http://localhost"})
    assert resposta.status_code not in (403, 415)


@pytest.mark.parametrize("rota", ["correcao", "desfazer", "exportar-txt", "chat"])
def test_header_secreto_nao_autoriza_host_externo(rota):
    client = app.test_client()
    caminho = f"/api/reunioes/inexistente/{rota}" if rota != "chat" else "/api/chat"
    resposta = client.post(
        caminho, json={"expected_revision": "rev-1"},
        headers={HEADER_TOKEN: obter_token_sessao()}, base_url="http://evil.example.test",
    )
    assert resposta.status_code == 403


def test_cookie_com_origin_exata_corrige_e_desfaz_resultado(tmp_path, monkeypatch):
    from resultado_reuniao import SegmentoResultado, salvar_segmentos

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    pasta = tmp_path / "resultados"
    pasta.mkdir()
    salvar_segmentos(
        pasta / "reuniao-teste.json",
        [SegmentoResultado("s1", 0, 1000, "loopback", "oi", "FALANTE_00")],
        {},
    )
    client = app.test_client()
    client.set_cookie(COOKIE_TOKEN, obter_token_sessao())
    headers = {"Origin": "http://localhost"}
    corrigir = client.post(
        "/api/reunioes/reuniao-teste/correcao", headers=headers,
        json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00", "display_name": "Ana"},
    )
    assert corrigir.status_code == 200
    desfazer = client.post(
        "/api/reunioes/reuniao-teste/desfazer", headers=headers,
        json={"expected_revision": corrigir.get_json()["revision"]},
    )
    assert desfazer.status_code == 200


def test_exportacao_txt_explicita_nao_cria_arquivo_plaintext(tmp_path, monkeypatch):
    from resultado_reuniao import SegmentoResultado, salvar_segmentos

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    pasta = tmp_path / "resultados"
    pasta.mkdir()
    salvar_segmentos(
        pasta / "reuniao-teste.json",
        [SegmentoResultado("s1", 0, 1000, "loopback", "fala de teste", "FALANTE_00")],
        {},
    )
    client = app.test_client()
    resposta = client.post(
        "/api/reunioes/reuniao-teste/exportar-txt", json={},
        headers={HEADER_TOKEN: obter_token_sessao()},
    )
    assert resposta.status_code == 200
    assert resposta.mimetype == "text/plain"
    assert "attachment" in resposta.headers["Content-Disposition"]
    assert "fala de teste" in resposta.get_data(as_text=True)
    assert not list(tmp_path.rglob("*.txt"))


def test_exportacao_txt_protegida_le_resultado_cifrado_sem_salvar_txt(tmp_path, chave_teste, monkeypatch):
    from types import SimpleNamespace
    from politica_privacidade import ProtectionMode
    from resultado_storage import ResultadoStorage

    storage = ResultadoStorage(tmp_path, ProtectionMode.PROTECTED)
    ref = storage.save("reuniao-protegida", {
        "schema_version": 1, "revision": "rev-1", "mapeamento": {}, "historico": [],
        "segmentos": [{"segment_id": "s1", "start_ms": 0, "end_ms": 1000,
                      "audio_source": "loopback", "text": "fala protegida",
                      "speaker_cluster_id": "FALANTE_00"}],
    })
    monkeypatch.setattr("assistente._resultado_protegido", lambda _id: (storage, SimpleNamespace(segments_ref=ref)))
    resposta = app.test_client().post(
        "/api/reunioes/reuniao-protegida/exportar-txt", json={},
        headers={HEADER_TOKEN: obter_token_sessao()},
    )
    assert resposta.status_code == 200
    assert "fala protegida" in resposta.get_data(as_text=True)
    assert not list(tmp_path.rglob("*.txt"))
