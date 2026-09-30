# -*- coding: utf-8 -*-
"""Configurações centralizadas do Transkriptor.

Todos os módulos importam suas constantes daqui em vez de definir as próprias.
Isso evita magic numbers espalhados e facilita ajustes.
"""

import os

# ---- Versão do produto (fonte única) ----
VERSAO = "2.0.0"

# ---- Caminhos ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_TRANSCRICOES = os.path.join(BASE_DIR, "transcricoes")
PASTA_AUDIO = os.path.join(PASTA_TRANSCRICOES, "audio")
LOG_FILE = os.path.join(BASE_DIR, "transkriptor.log")
ICONE_FILE = os.path.join(BASE_DIR, "transkriptor.ico")
DIR_MODELO_VOZ = os.path.join(BASE_DIR, "_modelo_voz")
ARQUIVO_CHAVE_DPAPI = os.path.join(DIR_MODELO_VOZ, "transkriptor_key.dpapi")
ARQUIVO_PERFIL_VOZ = os.path.join(DIR_MODELO_VOZ, "perfil_usuario.npz")
ARQUIVO_PERFIL_VOZ_ENC = os.path.join(DIR_MODELO_VOZ, "perfil_usuario.enc")
CONFIG_USER_FILE = os.path.join(BASE_DIR, "config_user.json")
MIN_DISCO_LIVRE_GB = 2
RETENCAO_AUDIO_DIAS = 7
TIMEOUT_AVISO_GRAVACAO_SEG = 30  # diálogo "continuar gravando?" (FR-2.9)

# ---- Áudio / Whisper ----
SAMPLE_RATE = 16000
CHUNK_SEGUNDOS = 25.0
FLUSH_AUDIO_SEG = 5
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


def preferir_whisper(modelo: str, device: str, ctype: str, *, fixo: bool = False) -> tuple[str, str, str]:
    """T-15.D3: aplica dispositivo/precisão escolhidos nas Configurações.

    Em "auto" (fixo=False), CPU forçada troca para o modelo leve; float16 não
    roda em CPU, então a precisão cai para int8 ali.
    """
    import config_user

    cfg = config_user.carregar()
    dispositivo, precisao = cfg.get("whisper_dispositivo") or "auto", cfg.get("whisper_precisao") or "auto"
    if dispositivo == "cpu" and device != "cpu":
        modelo, device, ctype = (modelo if fixo else "small"), "cpu", "int8"
    elif dispositivo == "cuda" and device != "cuda":
        device, ctype = "cuda", "int8_float16"
    if precisao != "auto":
        ctype = precisao
    if device == "cpu" and "float16" in ctype:
        ctype = "int8"
    return modelo, device, ctype


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
# Guarda operacional para o modo automatico. Reunioes maiores podem informar
# explicitamente ``num_falantes`` sem passar por este limite.
MAX_FALANTES_AUTO_DIARIZACAO = 12

# ---- Identificação de voz (VOCÊ) ----
LIMIAR_IDENTIFICACAO_VOZ = 0.72
ROTULO_USUARIO = "VOCÊ"
CAPTURAR_MIC = True
DURACAO_CADASTRO_SEG = 20
LIMIAR_RMS_MIC = 0.05
MARGEM_ANTI_ECO = 1.5
APRENDIZADO_VOZ_AMOSTRAS_MAX = 8
APRENDIZADO_VOZ_TRECHO_MAX_MS = 6000
APRENDIZADO_VOZ_TRECHO_MIN_MS = 1500
APRENDIZADO_VOZ_TOTAL_MIN_MS = 4000
APRENDIZADO_VOZ_MIN_AMOSTRAS = 2
APRENDIZADO_VOZ_FRACAO_COHERENTE = 0.75

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
CHAT_MODELO_MAX_CHARS = 80
CHAT_TRANSCRICAO_MAX_CHARS = 120
CHAT_PERGUNTA_MAX_CHARS = 4000
CHAT_CONTEUDO_MAX_CHARS = 4000
CHAT_MAX_CONCORRENTES = 2
RESUMO_MAX_RODADAS = 3
RESUMO_MAX_CHAMADAS = 8
RESUMO_RETRY_TENTATIVAS = 2
RESUMO_RETRY_ESPERA_SEG = 10

# ---- Monitor de Meet ----
EXIGIR_JANELA_VISIVEL = False
INTERVALO_MONITOR_MEET = 5          # segundos entre verificações
CONFIRMACAO_INICIO_MEET = 2         # ciclos com sinal forte para confirmar início (10 s)
CONFIRMACAO_FIM_MEET = 3            # legado: debounce do DetectorMeet por título
# Fusão multi-fonte: apenas título/ponte fortes podem iniciar uma reunião.
# Microfone permanece somente como sinal diagnóstico na v1.5.
CONFIRMACAO_FIM_SEM_SINAL_FORTE = 6 # ciclos sem título/extensão para encerrar (30 s)
DETECTAR_POR_MICROFONE = True       # usar o registro de microfone em uso do Windows
# Zoom por classe de janela + microfone do zoom.exe. O título do Zoom muda com o
# idioma e com a versão, então regex sozinha deixava reuniões passarem.
DETECTAR_ZOOM = True
HEARTBEAT_MONITOR_CICLOS = 120      # log periódico do monitor (a cada ~10 min)
# Ciclos de tolerância antes de declarar o monitor travado. O heartbeat só prova
# vida para quem lê o log; o vigia transforma a ausência dele em erro visível.
FATOR_TRAVAMENTO_MONITOR = 3        # 3 x INTERVALO_MONITOR_MEET = 15 s
# Portão do consentimento: se a pergunta morrer sem responder, o portão precisa
# reabrir sozinho — senão uma falha cega todas as reuniões seguintes.
LIMITE_PORTAO_CONSENTIMENTO_SEG = TIMEOUT_AVISO_GRAVACAO_SEG + 30

# Diálogo de consentimento (UX-14.E3): geometria base em 96 dpi, escalada por
# consentimento_layout.layout_consentimento(dpi). Botão primário >= 36 px (alvo de toque).
CONSENTIMENTO_DPI_BASE = 96
CONSENTIMENTO_LARGURA_BASE = 520
CONSENTIMENTO_MARGEM_BASE = 22
CONSENTIMENTO_BOTAO_ALTURA_MIN = 36
CONSENTIMENTO_ICONE_BASE = 32
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
MEET_WS_MAX_BYTES = 16 * 1024          # envelope máximo no socket (spec: 4 KiB)
MEET_WS_EVENTOS_POR_SEG = 20           # taxa sustentada por conexão
MEET_WS_BURST = 40                     # rajada máxima por conexão
MEET_WS_MAX_CONEXOES = 4               # conexões autenticadas simultâneas
# T-15.E1: só a nossa extensão fala com a ponte. O ID sai da `key` do manifest
# (desenvolvimento); os IDs da Chrome Web Store/Edge Add-ons entram ao publicar.
EXTENSAO_IDS_PERMITIDOS = ("mkcfobdlgdaeplnklpfcioojjgjjoojo",)
# T-15.E5: páginas da extensão nas lojas (preencher ao publicar; ver extension/meet/LOJA.md).
EXTENSAO_URL_CHROME = None
EXTENSAO_URL_EDGE = None
# T-15.E2: porta + segredo da ponte para o host de Native Messaging (pasta do usuário).
ARQUIVO_SEGREDO_PONTE = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "Transkriptor", "ponte.segredo")
MEET_CONVITE_SEG = 300                 # validade do convite de pareamento
MEET_SESSAO_SEG = 90 * 24 * 3600       # validade da credencial; renovada a cada uso
ARQUIVO_PAREAMENTO_MEET = os.path.join(DIR_MODELO_VOZ, "meet_pareamento.json")  # só hashes

# ---- Spool de eventos Meet (SEC-13.D4) ----
MEET_EVENTOS_BUFFER = 500             # eventos em RAM antes do dreno
MEET_EVENTOS_DRENO_SEG = 30.0         # T-15.A3: lote de até 30 s (antes 1 s; um arquivo por evento)
MEET_EVENTOS_SEGMENTO_BYTES = 1024 * 1024  # segmento JSONL antes do selo
MEET_EVENTOS_SPOOL_MAX_BYTES = 256 * 1024 * 1024  # teto do spool cifrado/sessão
MEET_EVENTOS_RAIZ = "eventos_privados"

# ---- Recuperação de sessão (SEC-13.E2) ----
RECUPERACAO_SESSOES = "sessoes"
RECUPERACAO_REGISTRO = "registro.json"
RECUPERACAO_RESTRITO = "restrito"
TIMEOUT_JOIN_STOP_SEG = 30

# ---- Watchdog ----
INTERVALO_WATCHDOG = 10             # segundos entre verificações
LIMITE_REINICIOS = 3                # reinícios consecutivos antes de erro crítico
CAPTURA_SEM_FRAMES_FALHA_SEG = 10   # thread viva sem avanço é falha, não silêncio
CAPTURA_ERROS_CONSECUTIVOS_LIMITE = 3

# ---- Áudio por fonte (FR-13.C2) ----
AUDIO_BLOCO_MAX_SEG = 30.0            # leitura/STT em blocos; nunca materializar 2 h
AUDIO_CIFRADO_LEGADO_MAX_BYTES = 256 * 1024 * 1024  # .wav.enc AES-GCM monolítico
ECO_SIMILARIDADE_MIN = 0.5            # Jaccard lexical mínimo p/ deduplicar eco

# ---- Identidade conservadora (FR-13.D6) ----
IDENTIDADE_LIMIAR_LEGENDA = 0.5       # Jaccard mínimo p/ legenda provar autoria
IDENTIDADE_EPSILON_EMPATE = 0.05      # diferença mínima p/ desempatar candidatos
IDENTIDADE_PRECISAO_MIN = 0.98        # precisão seletiva p/ modo automático
IDENTIDADE_COBERTURA_MIN = 0.80       # cobertura elegível p/ modo automático
CALIBRACAO_IDENTIDADE_VERSAO = "d6-1"
MODO_AUTO_NOMES = False               # comparação de texto nunca confirma sozinha
# T-15.C3 / DP-15-02: alinhamento com o Meet aplica o nome sozinho (provisório até T-15.F1).
NOMES_AUTO_MEET = True
NOME_AUTO_CONFIANCA_MIN = 0.6         # confiança do segmento (cobertura × fator do alinhamento)
NOME_AUTO_PARTICIPACAO_MIN = 0.8      # fatia do cluster de voz para nomear o cluster inteiro
NOME_AUTO_DURACAO_MIN_S = 5.0         # fala mínima do participante no cluster
# T-15.C4 — transcrição do Meet (blocos por falante) e lacunas sem Whisper.
MEET_BLOCO_INTERVALO_MS = 5000        # falas do mesmo falante até este intervalo formam um bloco
MEET_BLOCO_FALAS_MAX = 6
MEET_LACUNA_MIN_MS = 2000             # legenda sem segmento do Whisper vira lacuna a partir disto
INCERTEZA_TEMPO_MAX_MS = 1500         # acima disso, tempo sozinho não nomeia
# T-15.A2 — relógio da extensão: ping/pong ponte↔background por conexão.
RELOGIO_PINGS_INICIAIS = 5            # rajada ao vincular a aba
RELOGIO_INTERVALO_INICIAL_S = 0.2     # espaço entre pings da rajada
RELOGIO_INTERVALO_S = 30.0            # depois, um ping a cada 30 s
RELOGIO_AMOSTRAS_MAX = 20             # amostras recentes por conexão
RELOGIO_PINGS_PENDENTES_MAX = 8       # pings sem resposta guardados
RELOGIO_FOLGA_FUTURO_MS = 1000        # fala "no futuro" além disso: relógio ruim, não carimba
# T-15.C2 — alinhamento legenda↔Whisper. Provisórios até a calibração (T-15.F1).
ALINHAMENTO_FAIXA_MS = (-4000, 1000)  # δ somado à legenda; negativo = legenda atrasada
ALINHAMENTO_PASSO_MS = 50
ALINHAMENTO_TOLERANCIA_TEXTO_MS = 700 # palavra igual a até isto conta como concordância
ALINHAMENTO_MIN_PARES = 8             # menos que isso: atraso padrão, confiança reduzida
ALINHAMENTO_ATRASO_PADRAO_MS = -1000  # latência típica da legenda quando não dá para estimar
ALINHAMENTO_JANELA_MS = 60_000        # refino por janela acompanha a deriva
ALINHAMENTO_REFINO_MS = 500
ALINHAMENTO_CONCORDANCIA_MIN = 0.3
ALINHAMENTO_FATOR_SO_TEMPO = 0.6      # confiança quando só o tempo sustenta o nome
ATRIBUICAO_TOLERANCIA_MS = 300        # folga nas bordas da fala
ATRIBUICAO_GAP_MAX_MS = 1500          # palavra entre falas vai à mais próxima até isto
FRAGMENTO_MIN_MS = 600                # corte menor que isto (e fraco) volta ao vizinho

# ---- Worker pós-reunião (FR-13.B3) ----
# Orçamentos injetáveis; não derivam da duração da reunião.
WORKER_HEARTBEAT_SEG = 5
WORKER_PROGRESSO_AVISO_SEG = 120
WORKER_PROGRESSO_FALHA_SEG = 600
WORKER_MODELO_INIT_SEG = 600
WORKER_CANCEL_FORCAR_SEG = 30
WORKER_MAX_TENTATIVAS = 2
