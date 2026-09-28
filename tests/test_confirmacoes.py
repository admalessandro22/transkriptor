# -*- coding: utf-8 -*-
"""UX-14.E4 — confirmações padronizadas: bandeja (MessageBoxW) e Central com o mesmo texto (T-14.E4)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import confirmacoes
from confirmacoes import (
    ACOES,
    CONSEQUENCIAS,
    MB_DEFBUTTON2,
    MB_ICONWARNING,
    MB_YESNO,
    confirmar_na_bandeja,
    consequencia,
    texto_para_messagebox,
)

REPO = Path(__file__).resolve().parent.parent


def test_todas_as_acoes_tem_consequencia():
    assert set(CONSEQUENCIAS) == set(ACOES) == {
        "pausar_gravacao", "sair_gravando", "modo_protegido", "apagar_perfil_voz", "exportar_legivel",
    }
    for acao, textos in CONSEQUENCIAS.items():
        assert textos["titulo"].endswith("?"), acao
        assert len(textos["consequencia"]) > 40, acao
        assert textos["confirmar"] and textos["confirmar"] not in ("OK", "Sim"), acao
    with pytest.raises(KeyError):
        consequencia("formatar_disco")


def test_central_e_bandeja_usam_o_mesmo_texto():
    from assistente import HEADER_TOKEN, app, obter_token_sessao
    import central_config

    class Bandeja:
        deteccao_ativa = True

    central_config.registrar_app(Bandeja())
    try:
        app.config["TESTING"] = True
        corpo = app.test_client().post(
            "/api/config", json={"chave": "deteccao_ativa", "valor": False},
            headers={HEADER_TOKEN: obter_token_sessao()},
        ).get_json()
    finally:
        central_config.registrar_app(None)
    assert corpo["titulo"] == CONSEQUENCIAS["pausar_gravacao"]["titulo"]
    assert corpo["consequencia"] == CONSEQUENCIAS["pausar_gravacao"]["consequencia"]

    chamadas = []

    def caixa(hwnd, texto, titulo, flags):
        chamadas.append((texto, titulo, flags))
        return 7  # IDNO

    confirmar_na_bandeja("pausar_gravacao", messagebox=caixa)
    texto, titulo, _flags = chamadas[0]
    assert texto == texto_para_messagebox("pausar_gravacao")
    assert corpo["titulo"] in texto and corpo["consequencia"] in texto
    assert titulo == "Transkriptor"


def test_botao_padrao_e_seguro():
    flags_vistos = []

    def caixa(hwnd, texto, titulo, flags):
        flags_vistos.append(flags)
        return 6  # IDYES

    assert confirmar_na_bandeja("sair_gravando", messagebox=caixa) is True
    flags = flags_vistos[0]
    assert flags & MB_YESNO and flags & MB_ICONWARNING and flags & MB_DEFBUTTON2, "padrão precisa ser Não"
    assert confirmar_na_bandeja("sair_gravando", messagebox=lambda *a: 7) is False
    assert confirmar_na_bandeja("sair_gravando", messagebox=lambda *a: 2) is False  # IDCANCEL
    assert confirmar_na_bandeja("sair_gravando", messagebox=lambda *a: (_ for _ in ()).throw(OSError())) is False


def test_bandeja_nao_tem_messagebox_com_texto_proprio():
    """Toda confirmação da bandeja passa por confirmacoes.confirmar_na_bandeja."""
    fonte = (REPO / "app_bandeja_menu.py").read_text(encoding="utf-8")
    assert "MessageBoxW" not in fonte
    arvore = ast.parse(fonte)
    acoes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and getattr(no.func, "id", "") == "confirmar_na_bandeja":
            acoes.add(no.args[0].value)
    assert acoes == {"pausar_gravacao", "sair_gravando", "modo_protegido", "apagar_perfil_voz"}


def test_apagar_perfil_na_bandeja_exige_confirmacao(monkeypatch):
    import app_bandeja_menu

    class App(app_bandeja_menu.MenuBandejaMixin):
        identificar_minha_voz = True
        apagados = 0

        def _status(self, *_a):
            pass

        def _atualizar_tooltip(self):
            pass

    monkeypatch.setattr(app_bandeja_menu, "apagar_arquivos_perfil", lambda: setattr(App, "apagados", App.apagados + 1))
    monkeypatch.setattr(app_bandeja_menu, "desativar_perfil_na_config", lambda *a: None)
    monkeypatch.setattr(app_bandeja_menu, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(app_bandeja_menu, "confirmar_na_bandeja", lambda acao, **k: False)
    app = App()
    app.apagar_perfil_voz()
    assert App.apagados == 0 and app.identificar_minha_voz is True
    monkeypatch.setattr(app_bandeja_menu, "confirmar_na_bandeja", lambda acao, **k: acao == "apagar_perfil_voz")
    app.apagar_perfil_voz()
    assert App.apagados == 1 and app.identificar_minha_voz is False
    # A Central já confirmou (409 → confirmado): não abre MessageBox de novo.
    monkeypatch.setattr(app_bandeja_menu, "confirmar_na_bandeja", lambda acao, **k: pytest.fail("MessageBox indevida"))
    app.apagar_perfil_voz_com(confirmar=lambda: True)
    assert App.apagados == 2


def test_fluxos_da_bandeja_delegam_a_confirmacoes(monkeypatch):
    import app_bandeja_menu

    pedidas = []
    monkeypatch.setattr(app_bandeja_menu, "confirmar_na_bandeja", lambda acao, **k: pedidas.append(acao) or False)
    app = app_bandeja_menu.MenuBandejaMixin.__new__(app_bandeja_menu.MenuBandejaMixin)
    assert app._confirmar_saida() is False
    assert app._confirmar_pausa_padrao() is False
    assert app._confirmar_modo_protegido() is False
    assert pedidas == ["sair_gravando", "pausar_gravacao", "modo_protegido"]
    assert confirmacoes.confirmar_na_bandeja is not None


def test_central_exportar_usa_o_mesmo_texto():
    """O diálogo de exportação (participantes.js) repete literalmente confirmacoes.py."""
    js = (REPO / "static" / "js" / "participantes.js").read_text(encoding="utf-8")
    textos = CONSEQUENCIAS["exportar_legivel"]
    assert textos["titulo"] in js and textos["consequencia"] in js
    assert f"confirmarRotulo: '{textos['confirmar']}'" in js
