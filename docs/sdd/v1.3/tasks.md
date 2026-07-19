# Tasks — Transkriptor v1.3

Executar **uma tarefa por vez**, na ordem. Toda tarefa segue TDD:
teste RED observado → implementação mínima → GREEN → gate → commit.

**Status:** `[ ]` pendente · `[~]` em andamento · `[x]` concluída
**Baseline:** `python -m pytest tests/ -q` → **170 passed** (2026-07-19).

---

## Fase 1 — Higiene, git e versão única

### T-F1-01 — Inicializar git e limpar a raiz

- **Spec:** FR-1.1
- **Arquivos:** `.gitignore`; remoção de `_a.txt`, `_srv.txt`, `_srv2.txt`, `terminals/`, `agent-tools/`
- **Passos:** completar `.gitignore` (`terminals/`, `agent-tools/`, `_*.txt`, `.venv/`);
  apagar o lixo listado (dumps de terminal de sessões antigas, não é código);
  `git init` + commit inicial.
- **AC:** `git status --porcelain` limpo após commit; `git check-ignore` confirma
  `transcricoes/x.tkpt`, `config_user.json`, `transkriptor.log`.
- **Teste:** estender `tests/test_gitignore_docs.py` com as novas entradas.
- **Commit:** `chore: inicializa repositório git e higieniza raiz do projeto`
- **Status:** [x]

### T-F1-02 — Versão única em config.py

- **Spec:** FR-1.2, FR-1.3
- **Arquivos:** `config.py`, `transkriptor.pyw`, `pyproject.toml`, `instalar.bat`, `AGENTS.md`, novo `tests/test_versao.py`
- **Passos:** `VERSAO = "1.3.0"` em `config.py`; título/tooltip da bandeja via f-string;
  `pyproject.toml` → `1.3.0`; instalador lê via `python -c "from config import VERSAO; print(VERSAO)"`;
  AGENTS.md aponta `docs/sdd/v1.3/`.
- **AC (RED primeiro):** `tests/test_versao.py` — `config.VERSAO` bate com `pyproject.toml`;
  nenhum literal de versão hardcoded em `transkriptor.pyw`.
- **Commit:** `refactor: centraliza versão do produto em config.VERSAO`
- **Status:** [x]

**GATE F1:** `python -m pytest tests/ -q` verde + `git log --oneline` com ≥ 2 commits.

---

## Fase 2 — Gravação local garantida

### T-F2-01 — WAV sempre gravado e movido para transcricoes/audio/

- **Spec:** FR-2.1, FR-2.8
- **Arquivos:** `transcricao_core.py`, `config.py` (`PASTA_AUDIO`, `MIN_DISCO_LIVRE_GB`), novo `tests/test_gravacao_garantida.py`
- **Passos:** `_abrir_arquivo` sempre abre o WAV (remover a condição `if self.diarizar_ao_final`);
  no `stop()`, após a diarização (ou imediatamente, se diarização desativada), o WAV é
  **movido** para `PASTA_AUDIO = transcricoes/audio/` com o nome-base da transcrição em vez
  de apagado — a limpeza no `finally` de `_rodar_diarizacao` passa a mover, não remover.
  Checagem de disco livre (`shutil.disk_usage`) com toast se < 2 GB.
- **AC (RED):** com diarização desativada, após `stop()` existe
  `transcricoes/audio/<base>_audio.wav` com frames > 0; com diarização ativa, o arquivo é
  movido ao fim dela; nenhum caminho apaga o áudio.
- **Commit:** `feat: preserva áudio da reunião em transcricoes/audio`
- **Status:** [x]

### T-F2-02 — Criptografia do áudio finalizado + recuperação de órfãos

- **Spec:** FR-2.2, SEC-2.1
- **Arquivos:** `crypto_storage.py`, `transcricao_core.py`, `transkriptor.pyw`, `tests/test_gravacao_garantida.py`
- **Passos:** `crypto_storage.criptografar_wav(caminho) -> caminho_enc` (lê bytes, grava
  `.wav.enc`, remove plaintext; no-op se criptografia inativa); chamada ao mover o WAV
  para `PASTA_AUDIO`. Na inicialização do app, varrer `PASTA_AUDIO` e criptografar WAVs
  plaintext órfãos (pós-crash). Assistente: teste garante que nenhuma rota serve arquivos
  de `audio/` (o filtro de extensão já bloqueia — cobrir com teste).
- **AC:** com criptografia ativa, após finalizar existe só `.wav.enc` legível via
  `ler_bytes_arquivo`; órfão plaintext é convertido no start; `/api/transcricoes` não
  lista nada de `audio/`.
- **Commit:** `feat: criptografa áudio retido e recupera órfãos no start`
- **Status:** [x]

### T-F2-03 — Retenção de 7 dias

- **Spec:** FR-2.3
- **Arquivos:** novo `retencao_audio.py`, `transkriptor.pyw`, `config.py` (`RETENCAO_AUDIO_DIAS = 7`), novo `tests/test_retencao_audio.py`
- **Passos:** `limpar_audios_vencidos(pasta_audio, pasta_transcricoes, dias, agora=None) -> list`
  função pura testável: remove `.wav`/`.wav.enc` com mtime além da retenção **apenas se**
  existir transcrição com o mesmo nome-base; áudio vencido sem transcrição → mantido e
  retornado em lista separada para notificação. Thread diária no app (start + a cada 24h)
  chama a função e notifica quando houver áudios órfãos.
- **AC (RED):** áudio de 8 dias com transcrição → removido; de 8 dias sem transcrição →
  mantido + reportado; de 2 dias → mantido; `agora` injetável para teste determinístico.
- **Commit:** `feat: aplica retenção de 7 dias aos áudios de reunião`
- **Status:** [x]

### T-F2-04 — Falha de Whisper não perde o áudio

- **Spec:** FR-2.4
- **Arquivos:** `transcricao_core.py`, `transkriptor.pyw`, `tests/test_gravacao_garantida.py`
- **Passos:** hoje, se `_carregar_modelo()` lança, `start()` falha antes de abrir arquivos
  e nada é gravado. Inverter: abrir arquivos e iniciar captura **antes** de carregar o
  modelo; se o modelo falhar, a captura continua gravando WAV (modo "só áudio") e o
  status/toast informa "Transcrição indisponível — gravando somente áudio para
  retranscrição". `stop()` nesse modo preserva o áudio e não gera texto.
- **AC (RED):** com `WhisperModel` mockado para lançar exceção, após `start()` + 2s +
  `stop()` existe WAV com frames em `PASTA_AUDIO` e o status contém "somente áudio".
- **Commit:** `feat: grava somente áudio quando o Whisper falha`
- **Status:** [x]

### T-F2-05 — Menu "Retranscrever áudio…"

- **Spec:** FR-2.5
- **Arquivos:** novo `retranscritor.py`, `transkriptor.pyw`, novo `tests/test_retranscritor.py`
- **Passos:** `retranscrever(caminho_audio, **opcoes) -> caminho_transcricao`: lê o WAV
  (descriptografando `.wav.enc` se preciso), fatia em blocos de `CHUNK_SEGUNDOS`, alimenta
  o mesmo fluxo do `Transcritor` (fatorar `_transcrever_bloco` para aceitar fonte de áudio
  injetável — sem duplicar lógica) e roda a diarização/identificação padrão. Menu lista
  áudios de `PASTA_AUDIO` (data + duração via header WAV) num diálogo tkinter simples e
  roda em thread com status na bandeja.
- **AC (RED):** dado um WAV sintético e um modelo Whisper fake (injetado) que devolve
  segmentos conhecidos, `retranscrever` gera transcrição e diarizada com os mesmos
  formatos de arquivo da reunião ao vivo; `.wav.enc` também funciona.
- **Commit:** `feat: adiciona retranscrição de áudios retidos pelo menu`
- **Status:** [x]

### T-F2-06 — Pausa com confirmação e aviso persistente

- **Spec:** FR-2.6, FR-2.7, UX-2.1
- **Arquivos:** `transkriptor.pyw`, `estado_icone.py`, `transkriptor_acoes.py`, `tests/test_transkiptor_estado.py`, `tests/test_estado_icone.py` (ou equivalente existente)
- **Passos:** `alternar_deteccao` ao pausar exibe MessageBox de confirmação (função
  injetável para teste, como `_confirmar_saida`); texto do menu vira "Pausar gravação
  automática (NÃO grava reuniões)"; `estado_icone` já tem estado pausado — garantir cor
  distinta + tooltip "PAUSADO — não está gravando"; no monitor, Meet detectado durante
  pausa dispara toast (com debounce de 1 por reunião); remover qualquer persistência de
  pausa (não há hoje — cobrir com teste de que o app inicia com `deteccao_ativa=True`).
- **AC (RED):** pausar sem confirmar não pausa; pausado + Meet detectado → toast único;
  novo `AppTranskriptor()` sempre inicia com detecção ativa.
- **Commit:** `feat: exige confirmação e avisa quando a gravação está pausada`
- **Status:** [x]

**GATE F2:** `python -m pytest tests/test_gravacao_garantida.py tests/test_retencao_audio.py tests/test_retranscritor.py tests/test_transkiptor_estado.py -v`
verde + verificação manual do plan.md (falha simulada de modelo → áudio salvo → retranscrição OK).

---

## Fase 3 — Atalho global Ctrl+Espaço

### T-F3-01 — Parser de combinação de teclas

- **Spec:** FR-3.2
- **Arquivos:** novo `hotkey_global.py`, novo `tests/test_hotkey_global.py`
- **Passos:** `parse_atalho(texto: str) -> tuple[int, int]` com `ctrl/alt/shift/win` +
  tecla final (`space`, `a`-`z`, `0`-`9`, `f1`-`f12`); case-insensitive, separador `+`;
  `MOD_ALT=0x1, MOD_CONTROL=0x2, MOD_SHIFT=0x4, MOD_WIN=0x8`, `VK_SPACE=0x20`;
  inválido → `ValueError`.
- **AC:** `"ctrl+space"` → `(0x2, 0x20)`; `"ctrl+shift+t"`; `"CTRL + SPACE"`;
  inválidos (`"space"`, `"ctrl+"`, `"ctrl+enter+x"`) levantam `ValueError`.
- **Commit:** `feat: adiciona parser de atalho global de teclado`
- **Status:** [x]

### T-F3-02 — Registro do hotkey com message loop

- **Spec:** FR-3.1, FR-3.4
- **Arquivos:** `hotkey_global.py`, `tests/test_hotkey_global.py`
- **Passos:** classe `HotkeyGlobal(combo_texto, on_ativar, on_falha=None)`:
  `start()` → thread daemon com `RegisterHotKey(None, id, mods, vk)` + loop `GetMessageW`
  até `WM_HOTKEY` (0x0312), despachando `on_ativar` em outra thread; `stop()` →
  `PostThreadMessageW(tid, WM_QUIT, 0, 0)` + `UnregisterHotKey`. Falha de registro →
  `on_falha(motivo)`, `disponivel=False`, sem exceção. API Win32 via `_user32()` mockável.
- **AC:** com mock: registro OK dispara `on_ativar` ao injetar `WM_HOTKEY`;
  `RegisterHotKey`→0 chama `on_falha` sem levantar; `stop()` chama `UnregisterHotKey`
  exatamente uma vez.
- **Commit:** `feat: registra atalho global via RegisterHotKey com message loop`
- **Status:** [x]

### T-F3-03 — Integração com a bandeja

- **Spec:** FR-3.3, FR-3.5, UX-3.1, SEC-3.1
- **Arquivos:** `transkriptor.pyw`, `config.py` (`ATALHO_GLOBAL_PADRAO = "ctrl+space"`), `tests/test_hotkey_global.py`
- **Passos:** em `_ao_bandeja_pronta` (após mutex), criar `HotkeyGlobal` com combo de
  `config_user.json["atalho_global"]` (default `ctrl+space`) e
  `on_ativar=self.alternar_transcricao_manual`; parar no `sair()`; texto do menu manual
  inclui o combo formatado ("Ctrl+Espaço"); toasts de início/fim via hotkey;
  `on_falha` → notificação "Atalho Ctrl+Espaço indisponível — em uso por outro programa".
- **AC:** com hotkey mockado, ativação alterna transcrição manual; falha de registro não
  impede a bandeja; `texto_transcricao_manual` inclui o combo.
- **Commit:** `feat: ativa transcrição manual por Ctrl+Espaço global`
- **Status:** [x]

### T-F3-04 — Migração do atalho .lnk (remover Ctrl+Alt)

- **Spec:** FR-3.6
- **Arquivos:** `scripts/criar_atalho_desktop.ps1`, `tests/test_atalho_desktop.py`, `docs/MANUAL-USUARIO.md`
- **Passos:** `$atalho.Hotkey = ""` ao criar/recriar o `.lnk`; manual documenta que a
  ativação agora é Ctrl+Espaço com o app aberto.
- **AC:** teste verifica a limpeza de `Hotkey` no `.ps1`; manual atualizado.
- **Commit:** `fix: remove hotkey Ctrl+Alt do atalho da Área de Trabalho`
- **Status:** [x]

**GATE F3:** `python -m pytest tests/test_hotkey_global.py tests/test_atalho_desktop.py -v`
verde + manual: Ctrl+Espaço fora do app inicia (toast) e para (toast) a transcrição.

---

## Fase 4 — Assistente Ollama confiável

### T-F4-01 — Fake Ollama para testes

- **Spec:** NFR-4.1
- **Arquivos:** novo `tests/fake_ollama.py`, `tests/conftest.py`
- **Passos:** servidor HTTP em thread (porta efêmera) imitando `/api/tags`, `/api/show`
  (com `context_length`) e `/api/chat` (stream NDJSON); fixture `fake_ollama` que
  monkeypatcha `config.OLLAMA_URL` e registra as requisições recebidas.
- **AC:** smoke: `api_modelos()` contra o fake retorna a lista configurada.
- **Commit:** `test: adiciona servidor Ollama falso para testes de integração`
- **Status:** [x]

### T-F4-02 — num_ctx dinâmico e orçamento de contexto

- **Spec:** FR-4.1, FR-4.2
- **Arquivos:** `assistente.py`, `config.py` (`OLLAMA_NUM_CTX_MAX = 16384`, `CHARS_POR_TOKEN_PT = 3.2`), novo `tests/test_assistente_ollama.py`
- **Passos:** `orcamento_chars(context_length) -> int` (reserva ~25%); `api_chat` consulta
  `/api/show` (cache por modelo), envia `options={"num_ctx": n}`, corta a transcrição pelo
  orçamento mantendo o aviso de truncagem; falha do `/api/show` → fallback ao corte fixo
  atual, sem erro.
- **AC:** payload contém `options.num_ctx`; modelo com `context_length=4096` recebe menos
  transcrição que um de 32768; fallback coberto.
- **Commit:** `feat: dimensiona contexto do Ollama pelo modelo (num_ctx)`
- **Status:** [x]

### T-F4-03 — Map-reduce para reuniões longas

- **Spec:** FR-4.3
- **Arquivos:** novo `resumo_longo.py`, `assistente.py`, `tests/test_assistente_ollama.py`
- **Passos:** `dividir_em_blocos(texto, tamanho)` respeitando linhas;
  `responder_longo(modelo, blocos, pergunta, chamar_ollama)` com `chamar_ollama` injetável;
  `api_chat` usa esse caminho quando a transcrição excede o orçamento; stream inicia com
  `[Reunião longa: resposta consolidada de N blocos]`.
- **AC:** 3 blocos → 3 chamadas de resumo + 1 final; blocos preservam linhas; transcrição
  curta não passa pelo map-reduce.
- **Commit:** `feat: responde reuniões longas via map-reduce de blocos`
- **Status:** [x]

### T-F4-04 — Timeouts, saúde e token via cookie

- **Spec:** FR-4.4, FR-4.5, SEC-4.1, SEC-4.2
- **Arquivos:** `assistente.py`, `tests/test_assistente_seguranca.py`, `tests/test_token_sessao.py`
- **Passos:** timeouts nomeados em `config.py`; `GET /api/saude`; `index()` com `?token=`
  válido responde `Set-Cookie: tkpt_token=...; HttpOnly; SameSite=Strict` + redirect para
  `/` limpo; `/api/*` aceita cookie ou header e rejeita query; validação de corpo
  (256 KB → 413) e histórico (400); JS do front para de anexar token nas chamadas.
- **AC:** query em `/api/*` → 403; cookie válido → 200; corpo 300 KB → 413; histórico com
  50 itens → 400; `/api/saude` com fake desligado → `ollama: false`.
- **Commit:** `sec: move token do assistente para cookie e adiciona timeouts`
- **Status:** [x]

**GATE F4:** `python -m pytest tests/test_assistente_api.py tests/test_assistente_ollama.py tests/test_assistente_seguranca.py tests/test_token_sessao.py -v` verde, sem rede externa.

---

## Fase 5 — Nomes das vozes robustos

### T-F5-01 — Deduplicar leitura de WAV

- **Spec:** FR-5.5
- **Arquivos:** novo `audio_utils.py`, `transcricao_core.py`, `diarizador.py`, `retranscritor.py`, novo `tests/test_audio_utils.py`
- **Passos:** mover `_ler_trecho_wav` (versão com `sample_rate` de `diarizador.py`) para
  `audio_utils.ler_trecho_wav`; todos importam dela; apagar duplicatas.
- **AC:** teste com WAV sintético (recortes, limites, inexistente); suíte inteira verde.
- **Commit:** `refactor: unifica leitura de trechos WAV em audio_utils`
- **Status:** [x]

### T-F5-02 — Extensão: capturar legendas com nome

- **Spec:** FR-5.1, FR-5.4
- **Arquivos:** `extension/meet/content.js`, `meet_bridge.py`, novo `tests/test_extensao_parsing.py`, fixtures em `tests/fixtures/meet/`
- **Passos:** content.js observa o contêiner de legendas e extrai pares (nome, texto) em
  camadas (região de legendas → `data-*` → classes atuais como último recurso), enviando
  `{nome, texto, ts_ms, tipo:"legenda"}`. `normalizar_evento` aceita `texto` opcional
  (sanitiza como o nome, trunca em 500). Fixtures: 2 amostras anonimizadas do DOM de
  legendas; validar a extração via teste Python com parser equivalente e manter a função
  JS espelhada (limitação sem runner JS documentada no teste).
- **AC:** `normalizar_evento({nome, texto,...})` preserva texto sanitizado; sem nome →
  descartado; texto > 500 → truncado; fixture produz o par (nome, texto) esperado.
- **Commit:** `feat: captura legendas com nome do Meet na extensão`
- **Status:** [x]

### T-F5-03 — Correlação por conteúdo de legenda

- **Spec:** FR-5.2, FR-5.3
- **Arquivos:** `correlacionador.py`, `tests/test_correlacionador.py`
- **Passos:** `similaridade_tokens(a, b)` (Jaccard, minúsculas);
  `correlacionar_por_legenda(start, end, texto_segmento, eventos)` — eventos
  `tipo=="legenda"` na janela, maior similaridade (mínimo 0.2);
  `mesclar_prioridade_rotulos` tenta legenda antes da frequência.
- **AC:** dois falantes com legendas intercaladas na mesma janela → nomes corretos pelo
  texto; sem legendas → comportamento atual (testes existentes intactos); prioridade
  FR-5.3 testada explicitamente.
- **Commit:** `feat: correlaciona falantes pelo texto das legendas do Meet`
- **Status:** [x]

### T-F5-04 — Guarda anti-eco e rótulo efetivo

- **Spec:** FR-5.6, FR-5.7
- **Arquivos:** `diarizador.py`, `transcricao_core.py`, `assistente.py`, `config.py` (`MARGEM_ANTI_ECO = 1.5`), `tests/test_diarizacao_voce.py`
- **Passos:** `reforcar_rotulo_por_mic` recebe `rms_loopback_por_segmento` opcional:
  segmento só vira VOCÊ se `rms_mic >= limiar` e `rms_mic > rms_loopback * MARGEM_ANTI_ECO`
  (quando loopback disponível). `transcricao_contem_voce(conteudo, rotulo)` recebe o rótulo
  efetivo lido da config; atualizar `api_transcricoes`.
- **AC:** eco (mic fraco, loopback forte) mantém rótulo; fala real vira VOCÊ; badge
  "com sua voz" funciona com `rotulo_usuario` customizado.
- **Commit:** `fix: evita rotular eco do alto-falante como VOCÊ`
- **Status:** [x]

**GATE F5:** `python -m pytest tests/test_correlacionador.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_extensao_parsing.py tests/test_diarizacao_voce.py tests/test_audio_utils.py -v` verde.

---

## Fase 6 — Robustez e desempenho da transcrição

### T-F6-01 — Restart do watchdog não perde o arquivo

- **Spec:** FR-6.1, FR-6.2
- **Arquivos:** `transcricao_core.py`, `watchdog.py`, `tests/test_watchdog.py`, `tests/test_transcricao_stop.py`
- **Passos:** fechamento de `_arq`/`_wav` sai do `finally` de `_processar` (só fecha se
  `self._stop.is_set()`); teste RED: matar a thread com exceção injetada, acionar
  `_reiniciar_processar`, escrever novo bloco e provar que o texto continua no arquivo.
  Toast específico após 3 falhas consecutivas de captura.
- **AC:** teste de restart passa; `stop()` continua fechando tudo (testes existentes verdes).
- **Commit:** `fix: preserva arquivos abertos ao reiniciar threads pelo watchdog`
- **Status:** [x]

### T-F6-02 — Módulo config_user com lock e escrita atômica

- **Spec:** FR-6.5, NFR-6.1
- **Arquivos:** novo `config_user.py`, `transkriptor.pyw`, `crypto_storage.py`, novo `tests/test_config_user_modulo.py`
- **Passos:** `carregar() -> dict`, `salvar(cfg)`, `atualizar(**kv)` com `threading.Lock`
  e escrita tmp + `os.replace`; substituir os quatro helpers duplicados.
- **AC:** 2 threads × 50 atualizações → JSON válido com todas as chaves; varredura garante
  que só `config_user.py` abre `config_user.json`.
- **Commit:** `refactor: centraliza config_user.json com lock e escrita atômica`
- **Status:** [x]

### T-F6-03 — Modelo Whisper auto por hardware + menu

- **Spec:** FR-6.3, FR-6.4
- **Arquivos:** `config.py`, `transcricao_core.py`, `transkriptor.pyw`, novo `tests/test_modelo_whisper_auto.py`
- **Passos:** `resolver_modelo_whisper(tem_cuda: bool, vram_gb: float) -> (modelo, device, compute_type)`:
  CUDA e vram ≥ 4 → `("medium", "cuda", "int8_float16")`; senão → `("small", "cpu", "int8")`.
  Detecção de VRAM via `torch.cuda.get_device_properties(0).total_memory` (encapsulada e
  mockável). `Transcritor._carregar_modelo` usa a resolução quando `modelo_whisper=="auto"`
  (novo default), com try/except que re-tenta em CPU/`small` se o carregamento CUDA falhar.
  Submenu "Modelo Whisper" (`auto/tiny/base/small/medium/large-v3`) persiste via
  `config_user.atualizar`; toast "vale a partir da próxima transcrição".
- **AC (RED):** resolução testada nos dois ramos (GTX 1650 4 GB → medium/cuda);
  fallback CUDA→CPU coberto com mock que lança; menu persiste e o `Transcritor` recebe o
  modelo escolhido.
- **Commit:** `feat: resolve modelo Whisper automaticamente pelo hardware`
- **Status:** [x]

**GATE F6:** `python -m pytest tests/test_watchdog.py tests/test_transcricao_stop.py tests/test_config_user_modulo.py tests/test_modelo_whisper_auto.py -v` verde.

---

## Fase 7 — Instalador

### T-F7-01 — Helper testável do instalador

- **Spec:** FR-7.7, FR-7.1, FR-7.3, FR-7.5
- **Arquivos:** novo `scripts/instalar_helper.py`, novo `tests/test_instalador_helper.py`
- **Passos:** funções puras com executor injetável: `python_compativel(version_info)`,
  `tem_gpu_nvidia(runner)`, `ollama_status(runner)`, `comando_torch(tem_gpu)`.
  CLI `--check python|gpu|ollama` imprime `OK`/`AVISO: ...`/`ERRO: ...` parseável pelo `.bat`.
- **AC:** todos os ramos com runners falsos (GPU presente/ausente; Ollama ausente/sem
  modelos/ok; Python 3.11 reprovado citando "3.12").
- **Commit:** `feat: adiciona helper testável de pré-checagens do instalador`
- **Status:** [ ]

### T-F7-02 — instalar.bat com venv, GPU, warm-up e Ollama

- **Spec:** FR-7.2, FR-7.3, FR-7.4, FR-7.5, UX-7.1
- **Arquivos:** `instalar.bat` (atual vira `instalar_legacy.bat`), `iniciar_bandeja.bat`, `scripts/resolver_pythonw.py`, novo `scripts/warmup_modelos.py`
- **Passos:** fluxo `[1/5] Python → [2/5] .venv → [3/5] torch (CPU/CUDA via helper) →
  [4/5] requirements + warm-up opcional → [5/5] atalho`. `resolver_pythonw.py` prefere
  `.venv\Scripts\pythonw.exe`. `warmup_modelos.py` baixa o Whisper resolvido (FR-6.3) e o
  ECAPA. Checagem Ollama com instrução/pull sugerido (`llama3.1:8b`; alternativa
  `llama3.2:3b` documentada para a GTX 1650).
- **AC:** instalação manual em prompt limpo sobe a bandeja pelo atalho; `iniciar_bandeja.bat`
  usa o venv; sem GPU não baixa wheels CUDA.
- **Commit:** `feat: instalador com venv, detecção de GPU e warm-up de modelos`
- **Status:** [ ]

### T-F7-03 — Desinstalador

- **Spec:** FR-7.6
- **Arquivos:** novo `desinstalar.bat`, `docs/MANUAL-USUARIO.md`
- **Passos:** remove atalhos (Desktop/Startup) e `.venv/`; pergunta explicitamente antes
  de tocar `transcricoes/` (incl. `audio/`), `_modelo_voz/`, `config_user.json`
  (default: preservar); echo das ações antes de executar.
- **AC:** roteiro manual documentado; dry-run visual conferido.
- **Commit:** `feat: adiciona desinstalador com preservação de dados do usuário`
- **Status:** [ ]

**GATE F7:** `python -m pytest tests/test_instalador_helper.py tests/test_atalho_desktop.py -v`
verde + instalação manual completa OK; então remover `instalar_legacy.bat`.

---

## Fase 8 — Refatoração final

### T-F8-01 — Front do assistente em arquivos próprios

- **Spec:** FR-8.1
- **Arquivos:** `assistente.py`, novos `templates/assistente.html`, `static/assistente.css`, `static/assistente.js`, `tests/test_assistente_api.py`
- **Passos:** mover a string `HTML` para template + estáticos (Flask `render_template`);
  nenhum comportamento novo; ajustar testes que inspecionam o HTML para ler o template.
- **AC:** suíte do assistente verde; `assistente.py` < 300 linhas.
- **Commit:** `refactor: extrai front do assistente para templates e estáticos`
- **Status:** [ ]

### T-F8-02 — Dividir transkriptor.pyw

- **Spec:** FR-8.2, FR-8.3
- **Arquivos:** `transkriptor.pyw`, novos `startup_windows.py`, `perfil_voz_flow.py`, `notificador.py`, testes correspondentes
- **Passos:** extrair startup do Windows para `startup_windows.py` (reusar
  `criar_atalho_desktop.ps1` parametrizado em vez de PowerShell inline); extrair fluxo de
  perfil de voz para `perfil_voz_flow.py`; remover fallback `win10toast`.
  Nenhum arquivo de produção > 500 linhas.
- **AC:** suíte completa verde; verificação de limite de linhas passa.
- **Commit:** `refactor: divide transkriptor.pyw em módulos coesos`
- **Status:** [ ]

**GATE F8 (final):** `python -m pytest tests/ -q` 100% verde + limite de 500 linhas +
roteiro manual de release do `plan.md` executado e registrado em `docs/VERIFICACAO.md`.
