# Spec — Transkriptor v1.3

Requisitos verificáveis. Cada `FR/NFR/SEC/UX` deve ter ao menos um teste automatizado
citando o ID em comentário ou docstring.

Decisões do usuário incorporadas (ver `concept.md` § Decisões): retenção de áudio 7 dias,
pausa com aviso, criptografia padrão mantida, modelo Whisper auto por hardware.

## F1 — Higiene e versionamento

- **FR-1.1** O projeto é um repositório git com `.gitignore` cobrindo: `transcricoes/`,
  `_modelo_voz/`, `config_user.json`, `extension/meet/config.js`, `*.log`, `terminals/`,
  `agent-tools/`, `_*.txt`, `.venv/`, `__pycache__/`, `.pytest_cache/`.
- **FR-1.2** Existe `VERSAO = "1.3.0"` única em `config.py`; bandeja (título/tooltip),
  `pyproject.toml` e instalador exibem esse valor.
- **FR-1.3** `AGENTS.md` aponta `docs/sdd/v1.3/` como versão em execução e registra
  v1.2/v1.2.1 como concluídas.
- **NFR-1.1** `python -m pytest tests/ -q` permanece 100% verde após a fase.

## F2 — Gravação local garantida (requisito central)

- **FR-2.1** O áudio da reunião (loopback, e mic quando ativo) é **sempre** gravado em
  WAV, mesmo com diarização desativada. Ao encerrar a transcrição, o WAV deixa de ser
  temporário: é movido para `transcricoes/audio/` com o mesmo nome-base da transcrição
  (`transcricao_YYYY-MM-DD_HHhMM_audio.wav`).
- **FR-2.2** Com criptografia ativa, ao finalizar a reunião o WAV é convertido para
  `.wav.enc` (AES-GCM via `crypto_storage`) e o plaintext removido. Durante a gravação o
  arquivo permanece `.wav` (streaming). Na inicialização do app, WAVs plaintext órfãos em
  `transcricoes/audio/` são criptografados (recuperação pós-crash).
- **FR-2.3** Retenção: novo `RETENCAO_AUDIO_DIAS = 7` em `config.py`. Thread diária (e na
  inicialização) remove áudios com mtime além da retenção **somente se existir transcrição
  correspondente** (mesmo nome-base). Áudio sem transcrição nunca é apagado
  automaticamente; gera notificação sugerindo retranscrever.
- **FR-2.4** Falha ao carregar o Whisper ou na thread de processamento **não** interrompe
  a captura de áudio: a gravação do WAV continua e, ao fim, o áudio é preservado com toast
  "Transcrição falhou — áudio salvo para retranscrição". Teste prova que com
  `WhisperModel` lançando exceção o WAV final existe e tem frames.
- **FR-2.5** Menu "Retranscrever áudio…" lista os áudios de `transcricoes/audio/`
  (data + duração) e executa o pipeline completo offline (transcrição por blocos +
  diarização + identificação + nomes) gerando os mesmos artefatos de uma reunião ao vivo.
  Implementado em módulo `retranscritor.py` reutilizando `Transcritor`/`diarizar` — sem
  duplicar lógica.
- **FR-2.6** Pausar a detecção exige confirmação (MessageBox "O Transkriptor NÃO gravará
  reuniões enquanto pausado. Continuar?"). Enquanto pausado: ícone em cor própria
  (`estado_icone`), tooltip "PAUSADO — não está gravando" e, se um Meet for detectado
  durante a pausa, toast "Meet detectado, mas a gravação está pausada".
- **FR-2.7** O estado de pausa **não persiste** entre sessões: todo início de app tem
  detecção ativa.
- **FR-2.8** Se o disco tiver menos de `MIN_DISCO_LIVRE_GB = 2` livres ao iniciar uma
  transcrição, toast de aviso (a gravação prossegue).
- **UX-2.1** O item de menu da pausa deixa claro o efeito: "Pausar gravação automática
  (NÃO grava reuniões)".
- **FR-2.9** *(adicionado 2026-07-19)* Ao iniciar gravação automática (Meet detectado), a
  gravação começa imediatamente e um diálogo Sim/Não com timeout de
  `TIMEOUT_AVISO_GRAVACAO_SEG` (30s) oferece recusar. Só o "Não" explícito recusa —
  timeout ou erro do diálogo continuam gravando. Recusar para a gravação e **apaga** os
  arquivos desta reunião (`Transcritor.descartar()`), sem preservar áudio. Início manual
  não pergunta.
- **FR-2.10** *(adicionado 2026-07-19)* A recusa vale até o fim da reunião atual: nenhum
  novo início automático até o detector confirmar "encerrou". A próxima reunião pergunta
  de novo.
- **SEC-2.1** Os áudios retidos respeitam a mesma criptografia das transcrições; nenhuma
  rota do assistente serve arquivos de `transcricoes/audio/`.

## F3 — Atalho global Ctrl+Espaço

- **FR-3.1** Novo módulo `hotkey_global.py` registra hotkey global via
  `ctypes.windll.user32.RegisterHotKey` em thread dedicada com message loop
  (`GetMessageW`), liberando com `UnregisterHotKey` no encerramento.
- **FR-3.2** Combo padrão **Ctrl+Espaço** (`MOD_CONTROL=0x2`, `VK_SPACE=0x20`);
  configurável em `config_user.json` chave `atalho_global` (`"ctrl+space"`,
  `"ctrl+shift+t"`…); parser `parse_atalho(texto) -> (modificadores, vk)` puro e testável.
- **FR-3.3** Ação: alternar transcrição manual (mesmo fluxo do menu), despachada fora da
  thread do message loop.
- **FR-3.4** Falha de registro (combo em uso) → notificação amigável e app segue sem
  hotkey; nenhuma exceção não tratada.
- **FR-3.5** Item de menu da transcrição manual exibe o combo ativo
  (`Iniciar transcricao manual (Ctrl+Espaço)`).
- **FR-3.6** `criar_atalho_desktop.ps1` zera a propriedade `.Hotkey` do `.lnk` (remove
  Ctrl+Alt legado).
- **UX-3.1** Toast ao ativar/desativar via hotkey.
- **SEC-3.1** Hotkey não é registrado quando outra instância detém o mutex.

## F4 — Assistente Ollama confiável

- **FR-4.1** `assistente.py` consulta `GET /api/show` do Ollama para obter
  `context_length` do modelo; envia `options: {"num_ctx": N}` no `/api/chat`, com N =
  min(suporte do modelo, `OLLAMA_NUM_CTX_MAX = 16384`).
- **FR-4.2** O orçamento de caracteres da transcrição deriva de `num_ctx`
  (`CHARS_POR_TOKEN_PT = 3.2`, reservando ~25% para system/pergunta/resposta).
- **FR-4.3** Transcrição maior que o orçamento aciona **map-reduce** (`resumo_longo.py`):
  divide em blocos, resume cada um, responde sobre o conjunto; stream inicia com
  `[Reunião longa: resposta consolidada de N blocos]`.
- **FR-4.4** Toda chamada ao Ollama tem timeout de conexão (5s) e de leitura (120s,
  configurável); erro vira mensagem amigável, nunca stack trace.
- **FR-4.5** `GET /api/saude` retorna `{ollama: bool, modelos: [...], versao: str}`.
- **SEC-4.1** Token entregue via cookie `HttpOnly` + `SameSite=Strict` no primeiro GET com
  `?token=` válido; `/api/*` aceita cookie ou header e **rejeita** token em query.
- **SEC-4.2** `POST /api/chat` rejeita corpo > 256 KB (413) e histórico >
  `MAX_HISTORICO_CHAT` itens (400).
- **NFR-4.1** Testes usam servidor Ollama falso local — nenhum teste depende de Ollama
  instalado ou de rede externa.

## F5 — Nomes das vozes (Meet) robustos

- **FR-5.1** Extensão captura **legendas com nome**: para cada bloco de legenda envia
  `{nome, texto, ts_ms, tipo: "legenda"}` (texto ≤ 500 chars, sanitizado). Seletores em
  camadas (região de legendas → atributos `data-*` → classes) com fixtures HTML em
  `tests/fixtures/meet/`.
- **FR-5.2** `correlacionador.py` ganha modo legenda: segmento diarizado recebe o nome
  cuja legenda tem maior similaridade textual (Jaccard de tokens, mínimo 0.2) na janela
  temporal; sem legenda, cai na regra atual de frequência.
- **FR-5.3** Prioridade de rótulo documentada e testada: legenda com texto > falante
  ativo > voz conhecida > VOCÊ > FALANTE_XX.
- **FR-5.4** `meet_bridge.normalizar_evento` aceita campo `texto` opcional (sanitizado,
  truncado); eventos sem `nome` continuam descartados.
- **FR-5.5** `_ler_trecho_wav` unificada em `audio_utils.py`, importada por
  `transcricao_core` e `diarizador`.
- **FR-5.6** Guarda anti-eco: segmento só vira VOCÊ por energia de mic se
  `rms_mic >= limiar` **e** `rms_mic > rms_loopback * MARGEM_ANTI_ECO` (default 1.5)
  quando o loopback do intervalo estiver disponível.
- **FR-5.7** `transcricao_contem_voce(conteudo, rotulo)` usa o `rotulo_usuario` efetivo da
  config, não a constante.

## F6 — Robustez e desempenho da transcrição

- **FR-6.1** Restart do watchdog não perde arquivos: `_processar` não fecha `_arq`/`_wav`
  ao sair por exceção enquanto `rodando=True`; fechamento ocorre no `stop()`. Teste prova
  que após restart o texto continua sendo escrito.
- **FR-6.2** Três falhas consecutivas de captura → toast "Sem áudio do sistema — verifique
  o dispositivo de saída".
- **FR-6.3** `modelo_whisper: "auto"` (novo default em `config_user.json`): resolução
  automática por hardware — GPU NVIDIA com ≥ 4 GB VRAM → `medium`, device `cuda`,
  `compute_type="int8_float16"`; caso contrário → `small`, `cpu`, `int8`. Função pura
  `resolver_modelo_whisper(tem_cuda, vram_gb) -> (modelo, device, compute_type)` testável.
  Hardware de referência do usuário: GTX 1650 4 GB → `medium`/CUDA.
- **FR-6.4** Submenu "Modelo Whisper" na bandeja (`auto/tiny/base/small/medium/large-v3`)
  persiste a escolha; vale a partir da próxima transcrição (toast informa).
- **FR-6.5** Acesso a `config_user.json` centralizado em `config_user.py` com
  `threading.Lock` e escrita atômica (tmp + `os.replace`); `transkriptor.pyw` e
  `crypto_storage.py` migram para ele.
- **NFR-6.1** Nenhum outro módulo abre `config_user.json` diretamente (teste de varredura).

## F7 — Instalador e distribuição

- **FR-7.1** `instalar.bat` verifica Python ≥ 3.12 antes de qualquer pip.
- **FR-7.2** Instala em venv `.venv/`; atalhos e `iniciar_bandeja.bat` usam
  `.venv\Scripts\pythonw.exe`.
- **FR-7.3** Detecta GPU NVIDIA (`nvidia-smi`): com GPU → torch cu128; sem GPU → torch CPU
  (sem tentar CUDA).
- **FR-7.4** Warm-up opcional (S/N): pré-baixa o modelo Whisper resolvido (FR-6.3) e o
  ECAPA via `scripts/warmup_modelos.py`.
- **FR-7.5** Detecta Ollama: ausente → instrução com link; presente sem modelos → oferece
  `ollama pull llama3.1:8b` (nota: na GTX 1650 4 GB o 8b roda com offload parcial;
  documentar alternativa `llama3.2:3b` para resposta mais rápida).
- **FR-7.6** `desinstalar.bat`: remove atalhos e `.venv/`; pergunta antes de tocar
  `transcricoes/` (incl. `audio/`), `_modelo_voz/` e `config_user.json` — dados do usuário
  nunca removidos sem confirmação explícita.
- **FR-7.7** Lógica de decisão em `scripts/instalar_helper.py` (funções puras testáveis);
  o `.bat` só orquestra.
- **UX-7.1** Etapas numeradas `[n/5]` com OK/AVISO/ERRO e resumo final de pendências.

## F8 — Refatoração final

- **FR-8.1** HTML/CSS/JS do assistente movidos para `templates/` e `static/`; nenhuma
  string HTML com mais de 20 linhas em `.py`.
- **FR-8.2** `transkriptor.pyw` reduzido a bootstrap + bandeja; startup do Windows em
  `startup_windows.py`; fluxo de perfil de voz em `perfil_voz_flow.py`. Nenhum arquivo de
  produção com mais de 500 linhas.
- **FR-8.3** Fallback morto `win10toast` removido do `notificador.py`.
- **NFR-8.1** Suíte completa verde; testes de menu existentes passam sem alteração de
  asserts.
