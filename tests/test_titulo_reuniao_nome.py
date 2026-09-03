# -*- coding: utf-8 -*-
"""T-12.A1 — Nomear reunião a partir do título do Meet (FR-12.A1)."""
import pytest

# RED: este módulo/função ainda não existe — teste deve falhar antes da implementação
def test_titulo_para_base_extracao():
    from deteccao_reuniao import titulo_para_base

    # Meet: <nome> -> slug
    assert titulo_para_base("Meet: Reunião Bolsistas PROINOVE - Google Chrome") == "Reuniao_Bolsistas_PROINOVE"
    assert titulo_para_base("Meet: Sprint Planning 123 - Google Chrome") == "Sprint_Planning_123"

    # Meet – código -> fallback None (não é nome amigável)
    assert titulo_para_base("Meet – abc-defg-hij - Google Chrome") is None
    assert titulo_para_base("abc-defg-hij - Google Meet") is None
    assert titulo_para_base("Meet – xyz-abcd-efg - Google Chrome") is None

    # Meet: com código também deve fallback?
    assert titulo_para_base("Meet: abc-defg-hij - Google Chrome") is None

    # Fora de chamada
    assert titulo_para_base("Meet - Google Chrome") is None
    assert titulo_para_base("") is None
    assert titulo_para_base(None) is None

    # Sanitização: acentos, excesso de espaços, chars especiais
    assert titulo_para_base("Meet:  Reunião   com   espaços  ") == "Reuniao_com_espacos"
    assert titulo_para_base("Meet: Projeto @ #Incubadoras! 2026") == "Projeto_Incubadoras_2026"

    # Limite de tamanho (40 chars slug)
    longo = "Meet: " + "A" * 100 + " - Google Chrome"
    slug = titulo_para_base(longo)
    assert slug is not None
    assert len(slug) <= 40
    assert slug == "A" * 40


def test_detector_expoe_titulo_atual():
    from deteccao_reuniao import DetectorReuniao, FonteTitulo

    # Simula janela com Meet: nome
    def janelas_com_titulo():
        return [{"titulo": "Meet: Reunião Bolsistas PROINOVE - Google Chrome", "visivel": True}]

    det = DetectorReuniao([FonteTitulo(janelas_com_titulo)], confirma_inicio=1, confirma_fim=1)
    det.verificar()  # deve iniciar
    assert det.reuniao_ativa is True
    titulo = det.titulo_reuniao_atual()
    assert titulo == "Reuniao_Bolsistas_PROINOVE"

    # Com código, não deve expor slug
    def janelas_codigo():
        return [{"titulo": "Meet – abc-defg-hij - Google Chrome", "visivel": True}]

    det2 = DetectorReuniao([FonteTitulo(janelas_codigo)], confirma_inicio=1, confirma_fim=1)
    det2.verificar()
    assert det2.titulo_reuniao_atual() is None


def test_transcritor_usa_titulo_como_base():
    import tempfile
    from pathlib import Path
    from deteccao_reuniao import titulo_para_base
    from transcricao_core import Transcritor

    # Checa que Transcritor aceita titulo_reuniao e cria arquivo com slug
    with tempfile.TemporaryDirectory() as tmp:
        slug = titulo_para_base("Meet: Reuniao Teste - Google Chrome")
        assert slug == "Reuniao_Teste"
        tr = Transcritor(
            modelo="auto",
            pasta_saida=tmp,
            diarizar_ao_final=False,
            capturar_mic=False,
            identificar_voz=False,
            criptografar=False,
            processar_ao_vivo=True,
            titulo_reuniao=slug,
        )
        # Simula _abrir_arquivo sem precisar de modelo
        tr._abrir_arquivo()
        base = Path(tr._caminho_saida).stem
        assert slug in base, f"base {base} deveria conter slug {slug}"
        assert base.startswith("transcricao_")
        tr._fechar_arquivos_abertos()
        # fallback sem titulo
        tr2 = Transcritor(
            modelo="auto",
            pasta_saida=tmp,
            diarizar_ao_final=False,
            capturar_mic=False,
            identificar_voz=False,
            criptografar=False,
            processar_ao_vivo=True,
            titulo_reuniao=None,
        )
        tr2._abrir_arquivo()
        base2 = Path(tr2._caminho_saida).stem
        assert base2.startswith("transcricao_")
        assert slug not in base2
        tr2._fechar_arquivos_abertos()


def test_nome_base_com_titulo_preserva_timestamp_e_sanitiza():
    from deteccao_reuniao import titulo_para_base
    from crypto_storage import nome_base_transcricao

    # nome_base_transcricao com titulo deve gerar timestamp + slug
    base = nome_base_transcricao(titulo_reuniao="Reuniao_Teste", timestamp="2026-09-03_16h39")
    assert base == "transcricao_2026-09-03_16h39_Reuniao_Teste"
    base2 = nome_base_transcricao(titulo_reuniao=None, timestamp="2026-09-03_16h39")
    assert base2 == "transcricao_2026-09-03_16h39"
    # titulo sujo deve ser sanitizado
    base3 = nome_base_transcricao(titulo_reuniao="Reunião com acentos @!", timestamp="2026-09-03_16h39")
    assert base3 == "transcricao_2026-09-03_16h39_Reuniao_com_acentos"


def test_extensao_titulo_tem_prioridade_sobre_janela():
    from deteccao_reuniao import DetectorReuniao, FonteTitulo, FontePonte
    from meet_bridge import MeetBridge

    bridge = MeetBridge()
    # Simula heartbeat da extensão com titulo limpo
    bridge.registrar_evento({"tipo": "reuniao", "ativa": True, "titulo": "Meet: Reuniao Extensao Top - Google Chrome"})
    # Janela com outro titulo
    def janelas():
        return [{"titulo": "Meet: Reuniao Janela Secundaria - Google Chrome", "visivel": True}]

    det = DetectorReuniao([FonteTitulo(janelas), FontePonte(bridge)], confirma_inicio=1, confirma_fim=1)
    det.verificar()
    # Extensão deve ganhar (titulo mais limpo, sem sufixo navegador)
    assert det.titulo_reuniao_atual() == "Reuniao_Extensao_Top"


def test_transcritor_header_contem_titulo():
    import tempfile
    from pathlib import Path
    from transcricao_core import Transcritor

    with tempfile.TemporaryDirectory() as tmp:
        tr = Transcritor(
            pasta_saida=tmp,
            diarizar_ao_final=False,
            capturar_mic=False,
            identificar_voz=False,
            criptografar=False,
            titulo_reuniao="Reuniao_Teste_Header",
        )
        tr._abrir_arquivo()
        conteudo = Path(tr._caminho_saida).read_text(encoding="utf-8") if not tr.criptografar else tr._arq.getvalue()
        assert "Reuniao_Teste_Header" in conteudo
        assert "Reuniao:" in conteudo
        tr._fechar_arquivos_abertos()
