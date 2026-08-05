# -*- coding: utf-8 -*-
"""Configurações centralizadas do Transkriptor.

Todos os módulos importam suas constantes daqui em vez de definir as próprias.
Isso evita magic numbers espalhados e facilita ajustes.
"""

import os

# ---- Versão do produto (fonte única) ----
VERSAO = "1.4.0"

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
TIMEOUT_AVISO_GRAVACAO_SEG = 30  # diálogo "continuar gravando?" (FR-2.9)

# ---- Áudio / Whisper ----
SAMPLE_RATE = 16000
CHUNK_SEGUNDOS = 25.0
MODELO_WHISPER = "auto"  # FR-6.3: resolve pelo hardware em runtime
MODELOS_WHISPER_MENU = ("auto", "tiny", "base", "small", "medium", "large-v3")
# Uma placa "de 4 GB" reporta 3.9997 GiB (a GTX 1650 do usuário reporta
# 4294639616 bytes). Com o limiar em 4.0 exato, o hardware de referência caía
# sempre em small/CPU — mais lento e menos preciso. 3.8 cobre a folga.
VRAM_MIN_MEDIUM_GB = 3.8
IDIOMA = "pt"
COMPUTE_TYPE = "int8"
DEVICE_WHISPER = "auto"


def resolver_device_whisper(valor: str) -> str:
    if valor != "auto":
        return valor
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def resolver_modelo_whisper(tem_cuda: bool, vram_gb: float) -> tuple[str, str, str]:
    """FR-6.3: escolhe (modelo, device, compute_type) pelo hardware.

    CUDA com VRAM ≥ 4 GB → medium/cuda/int8_float16 (ex.: GTX 1650 4 GB).
    Caso contrário → small/cpu/int8.
    """
    if tem_cuda and float(vram_gb) >= VRAM_MIN_MEDIUM_GB:
        return ("medium", "cuda", "int8_float16")
    return ("small", "cpu", "int8")


def detectar_vram_gb() -> float:
    """VRAM do dispositivo CUDA 0 em GB; 0.0 se indisponível."""
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0
        props = torch.cuda.get_device_properties(0)
        return float(props.total_memory) / float(1024**3)
    except Exception:
        return 0.0


def detectar_cuda_e_vram() -> tuple[bool, float]:
    """Retorna (tem_cuda, vram_gb) para resolver_modelo_whisper."""
    try:
        import torch

        tem = bool(torch.cuda.is_available())
    except Exception:
        return (False, 0.0)
    if not tem:
        return (False, 0.0)
    return (True, detectar_vram_gb())

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
MARGEM_ANTI_ECO = 1.5

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
CONFIRMACAO_INICIO_MEET = 2         # ciclos com sinal forte para confirmar início (10 s)
CONFIRMACAO_FIM_MEET = 3            # legado: debounce do DetectorMeet por título
# Fusão multi-fonte (FR-9.1): só sinal fraco (microfone) exige mais ciclos, e o
# fim é mais lento que o início — cortar no meio custa a reunião inteira.
CONFIRMACAO_INICIO_FRACA = 4        # ciclos só com microfone para confirmar (20 s)
CONFIRMACAO_FIM_REUNIAO = 6         # ciclos sem nenhuma fonte para encerrar (30 s)
DETECTAR_POR_MICROFONE = True       # usar o registro de microfone em uso do Windows
HEARTBEAT_MONITOR_CICLOS = 120      # log periódico do monitor (a cada ~10 min)
# ---- Aviso de gravação (FR-2.9 / FR-9.4) ----
PERGUNTAR_ANTES_DE_GRAVAR = True    # diálogo Sim/Não ao detectar reunião

# ---- Nomes no Meet (Fase 8) ----
PORTA_MEET_BRIDGE = 5051
JANELA_CORRELACAO_SEG = 1.5
ARQUIVO_VOZES_CONHECIDAS = os.path.join(DIR_MODELO_VOZ, "vozes_conhecidas.json")
ARQUIVO_VOZES_CONHECIDAS_ENC = os.path.join(DIR_MODELO_VOZ, "vozes_conhecidas.enc")
USAR_NOMES_MEET = False
MODO_LEGENDAS_MEET = False
MAX_MENSAGEM_MEET_WS = 4096
MAX_NOME_PARTICIPANTE = 80
MAX_TEXTO_LEGENDA = 500
MAX_FILA_MEET_WS = 500
TIMEOUT_JOIN_STOP_SEG = 30

# ---- Watchdog ----
INTERVALO_WATCHDOG = 10             # segundos entre verificações
LIMITE_REINICIOS = 3                # reinícios consecutivos antes de erro crítico
