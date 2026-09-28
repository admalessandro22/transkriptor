# -*- coding: utf-8 -*-
"""Sanitização de mensagens de status para logs (SEC-6)."""

import re

MSG_LOG_TRANSCRICAO_OMITIDA = "[conteúdo de transcrição omitido do log]"

# Eventos tipados (T-13.E4): código + campos operacionais permitidos.
# Texto de fala nunca compartilha esta API: campos livres são omitidos,
# campos desconhecidos e códigos desconhecidos levantam ValueError.
CAMPOS_LIVRES_OMITIDOS = frozenset({"detalhe", "texto", "mensagem", "conteudo"})

CODIGOS_EVENTO = {
    "meeting_detected": ("fontes",),
    "status_error": (),
    "diarizacao_status": (),
    "modelo_carregando": (),
    "erro_critico": (),
    "audio_descarte_falhou": (),
    "modelo_fallback_cpu": (),
    "modelo_indisponivel": (),
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

VALORES_EVENTO = {
    "dispositivo": frozenset({"loopback", "microfone"}),
    "motivo_codigo": frozenset({"sem_dispositivo", "captura_falhou", "sem_frames"}),
    "thread": frozenset({"captura", "microfone", "monitor"}),
    "tipo": frozenset({"join", "leave", "rename", "participants"}),
    "stage": frozenset({"reservado", "transcrevendo", "diarizando", "concluido", "erro"}),
}
FONTES_REUNIAO = frozenset({"titulo", "microfone", "zoom", "extensao"})

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
        if chave == "fontes":
            fontes = valor.split(",") if isinstance(valor, str) else []
            valido = bool(fontes) and len(fontes) <= 4 and len(fontes) == len(set(fontes)) and all(
                fonte in FONTES_REUNIAO for fonte in fontes
            )
        elif chave in VALORES_EVENTO:
            valido = isinstance(valor, str) and valor in VALORES_EVENTO[chave]
        else:
            valido = isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor >= 0
        if not valido:
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
    if texto in {
        "Carregando modelo base...",
        "Modelo pronto.",
        "Reunião detectada. Iniciando gravação...",
        "Reunião encerrada. Finalizando transcricao...",
        "Reunião encerrada e colocada na fila de transcrição.",
        "Esta reunião não será gravada.",
        "Gravação da reunião em andamento.",
        "Gravação automática pausada.",
        "Gravação automática retomada.",
        "Gravação descartada.",
        "Transcrição encerrada.",
        "Transcricao em andamento.",
        "Capturando audio...",
    }:
        return True
    return bool(re.fullmatch(r"Capturando audio\.\.\. \([0-9]{4,6} Hz\)", texto))


def sanitizar_para_log(msg: str) -> str:
    if str(msg).startswith(("Reunião detectada", "Reuniao detectada")):
        return emitir_evento("meeting_detected")
    if str(msg).startswith(("Erro", "ERRO")):
        return emitir_evento("status_error")
    if str(msg).startswith("Diarização concluída:"):
        return emitir_evento("diarizacao_status")
    if str(msg).startswith("Carregando modelo"):
        return emitir_evento("modelo_carregando")
    if mensagem_e_sistema(msg):
        return msg
    return MSG_LOG_TRANSCRICAO_OMITIDA


def sanitizar_toast_para_log(titulo: str, _mensagem: str) -> str:
    return f"[TOAST] {titulo}: [mensagem omitida]"
