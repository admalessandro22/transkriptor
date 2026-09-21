# -*- coding: utf-8 -*-
"""Sanitização de mensagens de status para logs (SEC-6)."""

PREFIXOS_MENSAGEM_SISTEMA = (
    # O ciclo de reunião fala por estas duas palavras. Sem elas, "Reunião
    # detectada...", "Reunião encerrada..." e "Gravação em andamento" eram
    # censuradas como se fossem fala — em 2026-08-07 o app travou e o log ficou
    # com uma única linha inútil (ver tests/test_status_seguro.py).
    "Reunião",
    "Reuniao",
    "Gravação",
    "Gravacao",
    "Esta reunião",
    "Carregando",
    "Modelo pronto",
    "Capturando",
    "Erro",
    "Iniciando",
    "Diarização",
    "Transcrição",
    "Transcricao",
    "Sem segmentos",
    "Watchdog",
    "Meet",
    "Salvo:",
    "Assistente",
    "Detec",
    "Ponte",
    "ERRO",
    "Separação",
    "Reiniciando",
    "Ja transcrevendo",
    "Finalizando",
    "encerrada",
    "ativa em",
    "rodando em",
    "pausada",
    "retomada",
    "desativada",
    "Abrindo",
    "Aguardando",
    "Cadastro",
    "perfil",
    "nomes Meet",
    "legendas",
    "Vozes separadas",
    "offline",
    "Parar",
    "Sair",
    "Encerrando",
)

MSG_LOG_TRANSCRICAO_OMITIDA = "[conteúdo de transcrição omitido do log]"

# Eventos tipados (T-13.E4): código + campos operacionais permitidos.
# Texto de fala nunca compartilha esta API: campos livres são omitidos,
# campos desconhecidos e códigos desconhecidos levantam ValueError.
CAMPOS_LIVRES_OMITIDOS = frozenset({"detalhe", "texto", "mensagem", "conteudo"})

CODIGOS_EVENTO = {
    "captura_iniciada": ("dispositivo", "frames"),
    "captura_encerrada": ("duracao_seg",),
    "transcricao_bloco": (),
    "transcricao_concluida": ("duracao_seg",),
    "diarizacao_concluida": ("falantes",),
    "erro_captura": ("motivo_codigo",),
    "watchdog_reinicio": ("thread", "tentativa"),
    "meet_evento": ("tipo",),
    "worker_etapa": ("stage", "unidades"),
    "recuperacao": ("itens", "recuperados"),
}

_PADROES_CREDENCIAL = None


def _padroes_credencial():
    global _PADROES_CREDENCIAL
    if _PADROES_CREDENCIAL is None:
        import re as _re

        _PADROES_CREDENCIAL = [
            _re.compile(r"(?i)\btoken\s*[:=]\s*\S+"),
            _re.compile(r"\bBearer\s+\S+"),
            _re.compile(r"\bsess-[A-Za-z0-9_-]+"),
            _re.compile(r"\bpair-[A-Za-z0-9_-]+"),
            _re.compile(r"MEET_WS_TOKEN\s*=\s*\"[^\"]*\""),
        ]
    return _PADROES_CREDENCIAL


def _sem_credencial(texto: str) -> str:
    for padrao in _padroes_credencial():
        texto = padrao.sub("<credencial>", texto)
    return texto


def emitir_evento(codigo: str, **campos) -> str:
    """Emite linha de log tipada; fala em campo livre sai omitida."""
    permitidos = CODIGOS_EVENTO.get(codigo)
    if permitidos is None:
        raise ValueError(f"código de evento desconhecido: {codigo}")
    partes = [f"[{codigo}]"]
    for chave, valor in campos.items():
        if chave in CAMPOS_LIVRES_OMITIDOS:
            partes.append(f"{chave}=[conteúdo omitido]")
            continue
        if chave not in permitidos:
            raise ValueError(f"campo não permitido para {codigo}: {chave}")
        if not isinstance(valor, (str, int, float, bool)):
            raise ValueError(f"campo não permitido para {codigo}: {chave}")
        partes.append(f"{chave}={valor}")
    return _sem_credencial(" ".join(partes))


def sanitizar_excecao(exc: BaseException) -> str:
    """Resume exceção sem vazar credenciais (token/sessão nunca no log)."""
    return _sem_credencial(f"{type(exc).__name__}: {exc}")


def mensagem_e_sistema(msg: str) -> bool:
    if not msg or not str(msg).strip():
        return True
    texto = str(msg).strip()
    for prefixo in PREFIXOS_MENSAGEM_SISTEMA:
        if texto.startswith(prefixo):
            return True
    if ".txt" in texto or "127.0.0.1" in texto:
        return True
    return False


def sanitizar_para_log(msg: str) -> str:
    if mensagem_e_sistema(msg):
        return msg
    return MSG_LOG_TRANSCRICAO_OMITIDA


def sanitizar_toast_para_log(titulo: str, _mensagem: str) -> str:
    return f"[TOAST] {titulo}: [mensagem omitida]"