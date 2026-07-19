# Spec — Transkriptor v1.2

Especificação normativa derivada da **auditoria sênior 2026-07-08**.
Todo requisito deve ser implementado e testado conforme `plan.md` e `tasks.md`.

**Convenção de IDs:** `FR-*` funcional · `NFR-*` não-funcional · `SEC-*` segurança · `UX-*` experiência

---

## 1. Requisitos Funcionais

### Fase 0 — Infraestrutura de qualidade

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-0.1 | Estrutura `tests/` com `pytest` configurado (`pyproject.toml` ou `pytest.ini`) | P0 |
| FR-0.2 | Módulo `tests/conftest.py` com fixtures: `tmp_transcricoes`, `flask_client` | P0 |
| FR-0.3 | Script `scripts/verificar_fase.py` que roda subset de testes por fase | P1 |

### Fase 1 — Correções críticas (P0 auditoria)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-1.1 | Assistente Flask inicia em **thread daemon** antes de health check e `webbrowser.open` | P0 |
| FR-1.2 | Health check aguarda até 10s com retry (intervalo 0,5s) antes de declarar falha | P0 |
| FR-1.3 | Função `caminho_transcricao_seguro(nome)` valida que path resolvido está dentro de `PASTA_TRANSCRICOES` | P0 |
| FR-1.4 | `/api/chat` e `/api/transcricoes` usam `caminho_transcricao_seguro`; rejeitam `../` com HTTP 403 | P0 |
| FR-1.5 | Frontend do assistente popula `<select>` via DOM API (`createElement`/`textContent`), sem `innerHTML` com dados do servidor | P0 |

### Fase 2 — Engenharia (P1 auditoria)

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-2.1 | `_erro_critico()` define ícone vermelho; reverte ao estado normal após 30s ou próximo `_atualizar_tooltip` | P1 |
| FR-2.2 | Estado "pausado" usa ícone/cor distinta de "aguardando" (ex.: cinza `#64748b`) | P1 |
| FR-2.3 | `config.py`: `DEVICE_WHISPER = "auto"` (`cpu` se sem CUDA, senão `cuda`) | P1 |
| FR-2.4 | `Transcritor._carregar_modelo()` usa `DEVICE_WHISPER` de config | P1 |
| FR-2.5 | `instalar.bat` resolve `pythonw.exe` via `where python` / `sys.executable`, sem path hardcoded | P1 |
| FR-2.6 | Mutex de instância única (`Transkriptor.lock` ou `msvcrt`) — segunda instância exibe toast e encerra | P1 |
| FR-2.7 | Log com `RotatingFileHandler` (5 MB × 3 backups) em `Transkriptor.pyw` | P1 |
| FR-2.8 | Remover `import winreg` não usado; usar `PORTA_ASSISTENTE` como primeira porta em `PORTAS_FALLBACK` | P2 |
| FR-2.9 | Default modelo Ollama: primeiro da lista `/api/tags` ou string vazia com erro amigável | P2 |

### Fase 3 — Criptografia em repouso

> Arquivos legíveis **somente** pelo Transkriptor e assistente autenticado. Ver `PLANO-FINAL.md` § F3.

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-3.1 | Módulo `crypto_storage.py`: AES-256-GCM + chave protegida por Windows DPAPI | P0 |
| FR-3.2 | Formato `.tkpt` com header `TKPT1`; plaintext nunca em disco se toggle on | P0 |
| FR-3.3 | `Transcritor` e diarizador gravam via `salvar_transcricao`; leitura via `ler_transcricao` | P0 |
| FR-3.4 | `assistente.py` — único caminho de leitura para API `/api/chat` e listagem | P0 |
| FR-3.5 | Toggle menu "Criptografar transcrições" (default `true`); persiste em `config_user.json` | P1 |
| FR-3.6 | Migração automática `.txt` → `.tkpt` na 1ª ativação | P1 |
| FR-3.7 | Toggle off → retrocompat `.txt` plaintext | P2 |
| FR-3.8 | `perfil_usuario` e `vozes_conhecidas` criptografados com mesma chave | P1 |

### Fase 4 — Menu de opções + UX bandeja

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-4.1 | Toast ao vivo: primeiros 60 chars quando Meet **não** está em foco | P1 |
| FR-4.2 | Menu: "Abrir log", "Transcrição manual" | P2 |
| FR-4.3 | Confirmar saída se `transcritor.rodando` | P2 |
| FR-4.4 | Progresso diarização `N/total` | P2 |
| FR-4.5 | Submenu "Opções" com todos os toggles da spec (ver PLANO-FINAL §3) | P1 |
| FR-4.6 | `config_user.json` com `versao_config: 2` | P1 |

### Fase 5 — UX assistente

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-5.1 | Após 15s sem primeiro token: texto "O modelo está pensando..." | P1 |
| FR-5.2 | Barra de progresso indeterminada no `#chat` | P1 |
| FR-5.3 | Navegação ↑↓ entre action-cards | P2 |
| FR-5.4 | Sidebar drawer em mobile | P1 |
| FR-5.5 | Botão copiar + `tamanho_kb` | P2 |
| FR-5.6 | Listar/preview `.tkpt` via decrypt na API | P1 |

### Fase 6 — Segurança API

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-6.1 | Token sessão `X-Transkriptor-Token` + `?token=`; sem token → 403 | P2 |
| FR-6.2 | Meet visível (opcional) | P2 |
| FR-6.3 | Truncar contexto Ollama 80k chars | P2 |

### Fase 9 — Manutenção e qualidade

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-9.1 | `.gitignore` completo incl. `.tkpt`, `chave_dpapi`, `perfil_usuario.enc` | P1 |
| FR-9.2 | `requirements-dev.txt` + `cryptography>=42` em requirements | P1 |
| FR-9.3 | `docs/VERIFICACAO.md` gates F0–F9 | P1 |
| FR-9.4 | `CHANGELOG.md` v1.2 | P1 |

### Fase 7 — Identificação da voz do usuário

> **Pré-requisito técnico:** loopback sozinho não captura a voz local na maioria dos Meets.
> Esta fase exige cadastro pelo microfone + captura dupla (mic + loopback).

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-7.1 | Módulo `identificador_voz.py`: `cadastrar_perfil(audio_chunks) -> salvar`, `carregar_perfil() -> ndarray \| None`, `identificar_cluster(embeddings_por_cluster, perfil) -> int \| None` | P1 |
| FR-7.2 | Perfil salvo em `_modelo_voz/perfil_usuario.npz` (embedding médio + metadata: data, versão); nunca logar embedding | P1 |
| FR-7.3 | `config.py`: `ARQUIVO_PERFIL_VOZ`, `LIMIAR_IDENTIFICACAO_VOZ=0.72`, `ROTULO_USUARIO="VOCÊ"`, `CAPTURAR_MIC=True`, `DURACAO_CADASTRO_SEG=20` | P1 |
| FR-7.4 | Wizard de cadastro: menu bandeja "Cadastrar minha voz" → grava 20s do microfone padrão → salva perfil → toast de sucesso/erro | P1 |
| FR-7.5 | `Transcritor`: thread opcional `_capturar_mic` grava WAV `_mic.wav` sincronizado com `_audio.wav` quando `CAPTURAR_MIC=True` | P1 |
| FR-7.6 | Na diarização: após clustering, comparar centróide de cada cluster com perfil (cosseno); cluster acima de `LIMIAR_IDENTIFICACAO_VOZ` → `ROTULO_USUARIO` | P1 |
| FR-7.7 | Reforço por mic: segmentos com energia RMS no mic > limiar e overlap temporal → forçar rótulo `ROTULO_USUARIO` mesmo se cluster incerto | P2 |
| FR-7.8 | Arquivo diarizado usa `VOCÊ` nas linhas do usuário; demais permanecem `FALANTE_XX` | P1 |
| FR-7.9 | Menu toggle "Identificar minha voz" (default on se perfil existe); persistir em `config_user.json` | P2 |
| FR-7.10 | Item menu "Apagar perfil de voz" remove `perfil_usuario.npz` | P2 |
| FR-7.11 | Assistente: badge "com sua voz" quando `_diarizado.txt` contém `VOCÊ` | P3 |

### Fase 8 — Nomes dos participantes no Meet (opcional, pós-F7)

> Requer fonte além do loopback. Ver `identificacao-participantes.md`.

| ID | Requisito | Prioridade |
|----|-----------|------------|
| FR-8.1 | Extensão Chrome `Transkriptor-meet`: lê participantes + falante ativo no DOM do Meet | P2 |
| FR-8.2 | Servidor WebSocket local `127.0.0.1:5051` recebe eventos `{nome, ts_ms, tipo: ativo\|lista}` | P2 |
| FR-8.3 | `correlacionador.py`: associa segmentos `(start,end)` ao nome mais frequente na janela `[start-1.5s, end+1.5s]` | P2 |
| FR-8.4 | Diarizado prioriza: nome Meet > perfil voz cadastrado > `VOCÊ` > `FALANTE_XX` | P2 |
| FR-8.5 | Banco local `vozes_conhecidas.json` + embeddings: renomear falante persiste para futuras reuniões (estilo Otter) | P3 |
| FR-8.6 | Fallback UI Automation Windows se extensão ausente (feature flag `USAR_UIA_MEET=False`) | P3 |
| FR-8.7 | Modo “legendas Meet” (estilo Tactiq): extensão lê Closed Captions do DOM com nome do falante; exige CC ativo no Meet | P1 |
| FR-8.8 | Aviso na bandeja se Meet sem legendas e modo 8A habilitado: “Ative legendas no Meet para identificar participantes” | P2 |

---

## 2. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| NFR-1 | Cobertura mínima 70% em `detector_meet.py`, `assistente.py` (funções puras), `watchdog.py` |
| NFR-2 | Nenhuma fase merge/commit sem gate verde |
| NFR-3 | Tempo de startup do assistente < 5s (p95) após correção FR-1.1 |
| NFR-4 | Compatível Windows 10/11, Python 3.12+ |
| NFR-5 | App continua funcionando sem Ollama (assistente offline, transcrição OK) |
| NFR-6 | Cadastro de voz adiciona < 5 MB em disco; perfil carrega em < 200 ms |
| NFR-7 | Captura dupla (mic+loopback) não ultrapassa +30 MB RAM vs. loopback só |

---

## 3. Segurança

| ID | Requisito |
|----|-----------|
| SEC-1 | Path traversal bloqueado (FR-1.3, FR-1.4) |
| SEC-2 | XSS refletido/armazenado bloqueado no assistente (FR-1.5) |
| SEC-3 | Flask bind apenas `127.0.0.1` (inalterado) |
| SEC-4 | Token de sessão com `secrets.token_urlsafe(32)` (FR-5.1) |
| SEC-5 | PowerShell startup: escapar aspas em paths com `'` doubling (FR-2.5 relacionado) |
| SEC-6 | Não logar conteúdo de transcrições nem prompts completos |
| SEC-7 | Perfil de voz armazenado apenas localmente; criptografado (FR-3.8) |
| SEC-8 | Chave mestra só via DPAPI; nunca em log ou plaintext no repo |
| SEC-9 | Falha de decrypt → erro genérico; não vazar chave ou ciphertext útil |

---

## 4. UX (complemento v1.1)

| ID | Requisito | Status v1.1 | Meta v1.2 |
|----|-----------|-------------|-----------|
| UX-1.1 | Ícone dinâmico por estado | Parcial | + pausado + erro |
| UX-1.2 | Toast início/fim/diarização | OK | Manter |
| UX-1.3 | Toast ao vivo durante transcrição | Não | FR-3.1 |
| UX-2.1 | Histórico de chat | OK | Manter |
| UX-2.2 | Stop + timer | Parcial | FR-4.1, FR-4.2 |
| UX-2.3 | Preview no dropdown | OK | + tamanho_kb |
| UX-2.4 | A11y focus/ARIA | Parcial | FR-4.3 |
| UX-2.5 | Mobile sidebar | Não | FR-4.4 |
| UX-3.1 | Cadastro de voz guiado (contagem regressiva 20s) | Não | FR-7.4 |
| UX-3.2 | Transcrição diarizada distingue `VOCÊ` vs outros | Não | FR-7.8 |

---

## 5. Critérios de Aceite Globais (v1.2)

- [ ] `python -m pytest tests/ -v` — 100% pass
- [ ] Abrir assistente do menu bandeja 10× — 10 sucessos
- [ ] `POST /api/chat` com `transcricao: "../../config.py"` — 403
- [ ] Preview com `<script>` no .txt — não executa no browser
- [ ] Segunda instância do app — encerra com mensagem
- [ ] Erro crítico watchdog — ícone vermelho visível
- [ ] Spec v1.1 UX-05 mensagem 15s — implementada
- [ ] Com perfil cadastrado + mic ativo, reunião de teste rotula falas do usuário como `VOCÊ`
- [ ] Sem perfil cadastrado, diarização inalterada (`FALANTE_XX` apenas)
- [ ] Arquivo `.tkpt` ilegível fora do app; assistente lê normalmente
- [ ] Extensão + CC on → nomes de participantes no diarizado

---

> **Numeração canônica de fases:** ver `PLANO-FINAL.md` (F0–F9). Este `spec.md` agrupa requisitos por ID `FR-*`.

---

## 6. Rastreabilidade

```
concept.md (visão)
    → spec.md (FR/NFR/SEC/UX)
        → plan.md (fases + gates)
            → tasks.md (T-* acionáveis)
                → docs/superpowers/plans/... (passos TDD)
```