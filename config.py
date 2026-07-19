# -*- coding: utf-8 -*-
"""Configurações centralizadas do Transkriptor.

Todos os módulos importam suas constantes daqui em vez de definir as próprias.
Isso evita magic numbers espalhados e facilita ajustes.
"""

import os

# ---- Versão do produto (fonte única) ----
VERSAO = "1.3.0"

# ---- Caminhos ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_TRANSCRICOES = os.path.join(BASE_DIR, "transcricoes")
PASTA_AUDIO = os.path.join(PASTA_TRANSCRICOES, "audio")
LOG_FILE = os.path.join(BASE_DIR, "transkriptor.log")
ICONE_FILE = os.path.join(BASE_DIR, "transkriptor.ico")
DIR_MODELO_VOZ = os.path.join(BASE_DIR, "_modelo_voz")
ARQUIVO_PERFIL_VOZ = os.path.join(DIR_MODELO_VOZ, "perfil_usuario.npz")
ARQUIVO_PERFIL_VOZ_ENC = os.path.join(DIR_MODELO_VOZ, "perfil_usuario.enc")
CONFIG_USER_FILE = os.path.join(BASE_DIR, "config_user.json")
MIN_DISCO_LIVRE_GB = 2
RETENCAO_AUDIO_DIAS = 7
ATALHO_GLOBAL_PADRAO = "ctrl+space"

# ---- Áudio / Whisper ----
SAMPLE_RATE = 16000
CHUNK_SEGUNDOS = 25.0
MODELO_WHISPER = "base"
IDIOMA = "pt"
COMPUTE_TYPE = "int8"
DEVICE_WHISPER = "auto"


def resolver_device_whisper(valor: str) -> str:
    if valor != "auto":
        return valor
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"

# ---- Diarização ----
MODELO_VOZ_FONTE = "speechbrain/spkrec-ecapa-voxceleb"
LIMIAR_COSSENO_DIARIZACAO = 0.25
DURACAO_MIN_SEGMENTO = 0.5

# ---- Identificação de voz (VOCÊ) ----
LIMIAR_IDENTIFICACAO_VOZ = 0.72
ROTULO_USUARIO = "VOCÊ"
CAPTURAR_MIC = True
DURACAO_CADASTRO_SEG = 20
LIMIAR_RMS_MIC = 0.05

# ---- Ollama / Assistente ----
OLLAMA_URL = "http://localhost:11434"
PORTA_ASSISTENTE = 5050
# 5051 reservada para PORTA_MEET_BRIDGE — não incluir em fallbacks do assistente
PORTAS_FALLBACK = [5050, 5052, 5053, 5060, 5070, 5080, 5090, 5100]
MAX_HISTORICO_CHAT = 20
MAX_CHARS_TRANSCRICAO = 80000
OLLAMA_NUM_CTX_MAX = 16384
CHARS_POR_TOKEN_PT = 3.2
OLLAMA_TIMEOUT_CONEXAO = 5
OLLAMA_TIMEOUT_LEITURA = 120
MAX_CORPO_CHAT_BYTES = 256 * 1024

# ---- Monitor de Meet ----
EXIGIR_JANELA_VISIVEL = False
INTERVALO_MONITOR_MEET = 5          # segundos entre verificações
CONFIRMACAO_INICIO_MEET = 2         # ciclos consecutivos para confirmar início
CONFIRMACAO_FIM_MEET = 3            # ciclos consecutivos para confirmar fim

# ---- Nomes no Meet (Fase 8) ----
PORTA_MEET_BRIDGE = 5051
JANELA_CORRELACAO_SEG = 1.5
ARQUIVO_VOZES_CONHECIDAS = os.path.join(DIR_MODELO_VOZ, "vozes_conhecidas.json")
ARQUIVO_VOZES_CONHECIDAS_ENC = os.path.join(DIR_MODELO_VOZ, "vozes_conhecidas.enc")
USAR_NOMES_MEET = False
MODO_LEGENDAS_MEET = False
MAX_MENSAGEM_MEET_WS = 4096
MAX_NOME_PARTICIPANTE = 80
MAX_FILA_MEET_WS = 500
TIMEOUT_JOIN_STOP_SEG = 30

# ---- Watchdog ----
INTERVALO_WATCHDOG = 10             # segundos entre verificações
LIMITE_REINICIOS = 3                # reinícios consecutivos antes de erro crítico
