# -*- coding: utf-8 -*-
"""Verifica fixtures compartilhadas (F0)."""


def test_tmp_transcricoes_cria_arquivo_isolado(tmp_transcricoes):
    arquivos = list(tmp_transcricoes.glob("*.txt"))
    assert len(arquivos) == 1
    conteudo = arquivos[0].read_text(encoding="utf-8")
    assert "Ola equipe" in conteudo
    assert "transcricoes" in str(tmp_transcricoes)