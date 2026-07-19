# Plan — Transkriptor v1.2

> **Substituído por [PLANO-FINAL.md](PLANO-FINAL.md)** (10 fases F0–F9, criptografia, menu opções, ordem lógica fechada).  
> Este arquivo mantém histórico da auditoria inicial.

Plano de implementação em **8 fases** (0–7). Cada fase termina com um **gate de verificação**.
Se o gate falhar: aplicar `superpowers:systematic-debugging`, corrigir, re-rodar gate — **não avançar**.

**Duração estimada total:** 24–32h (inclui Fase 7 identificação de voz)
**Método:** SDD + TDD (superpowers)  
**Plano detalhado TDD:** `docs/superpowers/plans/2026-07-08-Transkriptor-v1.2-audit-remediation.md`

---

## Visão geral das fases

| Fase | Nome | Foco | Estimativa | Requisitos |
|------|------|------|------------|------------|
| 0 | Fundação QA | pytest, fixtures, AGENTS | 2h | FR-0.*, NFR-2 |
| 1 | P0 Crítico | Assistente, path, XSS | 3h | FR-1.*, SEC-1, SEC-2 |
| 2 | P1 Engenharia | Erro, GPU, install, mutex, log | 4h | FR-2.* |
| 3 | UX Bandeja | Toasts ao vivo, menu, progresso | 3h | FR-3.*, UX-1.* |
| 4 | UX Assistente | UX-05 completo, mobile, copy | 4h | FR-4.*, UX-2.* |
| 5 | Segurança+ | Token, Meet visível, truncar contexto | 3h | FR-5.*, SEC-4 |
| 6 | Manutenção | gitignore, docs, dev deps | 2h | FR-6.* |
| 7 | Identificação de voz | Cadastro + mic + rótulo VOCÊ | 6h | FR-7.*, UX-3.*, SEC-7 |
| 8 | Nomes no Meet (opc.) | Extensão Chrome + WebSocket + correlação | 8h | FR-8.* |

> **Fase 8** é opcional e depende da F7. Detalhes em `identificacao-participantes.md`.

---

## Diagrama de dependências

```
Fase 0 (pytest)
    │
    ▼
Fase 1 (P0 crítico) ──────────────────────────┐
    │                                         │
    ▼                                         │
Fase 2 (engenharia)                           │
    │                                         │
    ├──────────────► Fase 3 (UX bandeja)      │
    │                      │                  │
    └──────────────► Fase 4 (UX assistente)   │
                           │                  │
                           ▼                  │
                    Fase 5 (segurança+) ◄─────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       Fase 6 (manutenção)      Fase 7 (identificação voz)
              │                         │
              └────────────┬────────────┘
                           ▼
                  GATE FINAL (F6 + F7)
```

Fases 3 e 4 podem rodar em paralelo **após** Fase 2 verde.  
**Fase 7** depende de Fase 2 (config) e do `diarizador.py` estável; pode rodar em paralelo com 3–5, mas o **gate final** exige F6 **e** F7 verdes.

---

## Fase 0 — Fundação de Qualidade

**Objetivo:** Criar alicerce de testes antes de qualquer correção de produção.

### Entregáveis

- `pyproject.toml` com `[tool.pytest.ini_options]`
- `requirements-dev.txt`
- `tests/conftest.py`
- `tests/test_detector_meet.py` (baseline — já deve passar com código atual)
- `scripts/verificar_fase.py`

### Gate F0 — `AC-F0`

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_detector_meet.py -v
python scripts/verificar_fase.py --fase 0
```

**Critérios:**
- [ ] pytest descobre `tests/`
- [ ] ≥ 8 testes em `test_detector_meet.py` passam
- [ ] `verificar_fase.py --fase 0` exit code 0

**Se falhar:** corrigir imports/fixtures; não iniciar Fase 1.

---

## Fase 1 — Correções Críticas (P0)

**Objetivo:** Assistente funcional + API segura contra path traversal e XSS.

### Entregáveis

- `assistente.py`: `caminho_transcricao_seguro()`, refactor startup
- `Transkriptor.pyw`: `_iniciar_assistente()` com thread Flask primeiro
- `tests/test_assistente_seguranca.py`
- `tests/test_assistente_startup.py`

### Gate F1 — `AC-F1`

```bash
python -m pytest tests/test_assistente_seguranca.py tests/test_assistente_startup.py -v
python scripts/verificar_fase.py --fase 1
```

**Critérios:**
- [ ] Path `../../windows` → 403
- [ ] Health check passa quando servidor sobe antes do browser (mock ou integração)
- [ ] Testes de escape XSS no builder de options (unitário JS via extração ou teste Python do helper)

**Teste manual pós-gate:**
1. Menu bandeja → "Abrir assistente" → página carrega (1ª tentativa).
2. Repetir 3× consecutivas.

**Se falhar:** `systematic-debugging` no fluxo `_iniciar_assistente`; verificar ordem thread/sleep/urlopen.

---

## Fase 2 — Engenharia P1

**Objetivo:** Confiabilidade operacional e feedback de erro.

### Entregáveis

- `Transkriptor.pyw`: ícone erro, pausado, log rotation, mutex
- `config.py`: `DEVICE_WHISPER`
- `transcricao_core.py`: device configurável
- `instalar.bat`: pythonw dinâmico
- `tests/test_config_device.py`, `tests/test_mutex.py`, `tests/test_Transkriptor_estado.py`

### Gate F2 — `AC-F2`

```bash
python -m pytest tests/test_config_device.py tests/test_mutex.py tests/test_Transkriptor_estado.py -v
python scripts/verificar_fase.py --fase 2
```

**Critérios:**
- [ ] `DEVICE_WHISPER="auto"` retorna `cpu` ou `cuda` conforme `torch.cuda.is_available()`
- [ ] Mutex: segunda aquisição falha (teste com arquivo lock)
- [ ] `_erro_critico` seta estado ícone `erro` (teste unitário com mock pystray)

**Se falhar:** isolar componente que falhou; não misturar fixes de Fase 3.

---

## Fase 3 — UX Bandeja

**Objetivo:** Completar feedback operacional na bandeja.

### Entregáveis

- Toast ao vivo (FR-3.1)
- Itens menu: log, transcrição manual, confirmar saída
- Progresso diarização em `diarizador.py`
- `tests/test_notificador.py`, `tests/test_diarizador_progresso.py`

### Gate F3 — `AC-F3`

```bash
python -m pytest tests/test_notificador.py tests/test_diarizador_progresso.py -v
python scripts/verificar_fase.py --fase 3
```

**Teste manual:**
- [ ] Ícone pausado ≠ aguardando
- [ ] Toast ao vivo dispara quando Meet em background (simular com flag de teste)
- [ ] Diarização reporta `12/45 segmentos...`

---

## Fase 4 — UX Assistente

**Objetivo:** Completar UX-05 e mobile.

### Entregáveis

- Timer mensagem 15s, barra progresso, drawer mobile, copiar, tamanho_kb
- `tests/test_assistente_api.py` (metadados)

### Gate F4 — `AC-F4`

```bash
python -m pytest tests/test_assistente_api.py -v
python scripts/verificar_fase.py --fase 4
```

**Teste manual (browser):**
- [ ] Timer muda texto após 15s (devtools → throttle)
- [ ] Barra indeterminada visível durante fetch
- [ ] Viewport 375px — drawer abre e select funciona
- [ ] Copiar cola texto da última resposta

---

## Fase 5 — Segurança Avançada

**Objetivo:** Endurecer superfície local.

### Entregáveis

- Token sessão Flask
- Meet visível (opcional via `config_user.json`)
- Truncagem contexto Ollama
- `tests/test_token_sessao.py`, `tests/test_detector_meet_visivel.py`

### Gate F5 — `AC-F5`

```bash
python -m pytest tests/test_token_sessao.py tests/test_detector_meet_visivel.py -v
python scripts/verificar_fase.py --fase 5
```

**Critérios:**
- [ ] Request sem token → 403
- [ ] Transcrição > MAX_CHARS → flag `truncada: true` na resposta ou header

---

## Fase 6 — Manutenção

**Objetivo:** Higiene de repo e documentação operacional.

### Entregáveis

- `.gitignore`, `requirements-dev.txt` finalizado
- `docs/VERIFICACAO.md`
- Gate completo

### Gate F6 — `AC-F6`

```bash
python -m pytest tests/test_gitignore_docs.py -v  # ou subset fase 6
python scripts/verificar_fase.py --fase 6
```

**Critérios:**
- [ ] `.gitignore` cobre artefatos listados em FR-6.1 + `perfil_usuario.npz`
- [ ] `docs/VERIFICACAO.md` documenta gates F0–F7

---

## Fase 7 — Identificação da Voz do Usuário

**Objetivo:** Saber o que *você* falou em cada reunião, rotulado como `VOCÊ` no arquivo diarizado.

### Por que não basta o loopback

O áudio do alto-falante traz principalmente **vozes remotas**. Sua voz vai pelo **microfone**
para o Meet. A Fase 7 combina:

1. **Perfil de voz** (cadastro único via mic)
2. **Gravação paralela do mic** durante a reunião
3. **Matching ECAPA** na diarização (reusa `speechbrain` já instalado)

### Entregáveis

- `identificador_voz.py` — cadastro, carga, matching
- `transcricao_core.py` — thread `_capturar_mic`, WAV `_mic.wav`
- `diarizador.py` — integração `identificar_cluster` + reforço RMS mic
- `Transkriptor.pyw` — menus cadastrar/apagar/toggle identificação
- `tests/test_identificador_voz.py`, `tests/test_captura_mic.py`, `tests/test_diarizacao_voce.py`

### Gate F7 — `AC-F7`

```bash
python -m pytest tests/test_identificador_voz.py tests/test_captura_mic.py tests/test_diarizacao_voce.py -v
python scripts/verificar_fase.py --fase 7
```

**Critérios automatizados:**
- [ ] `cadastrar_perfil` + `carregar_perfil` round-trip preserva embedding
- [ ] `identificar_cluster` retorna índice correto com embeddings mock (similaridade > 0.72)
- [ ] `diarizar(..., perfil_usuario=mock)` produz linhas com `VOCÊ` no cluster esperado
- [ ] Sem perfil → saída idêntica ao comportamento atual (`FALANTE_XX` only)

**Teste manual (obrigatório):**
1. Menu → "Cadastrar minha voz" → ler texto sugerido por 20s.
2. Entrar em Meet de teste (ou simular áudio mic+loopback).
3. Encerrar → abrir `*_diarizado.txt` → verificar linhas `[VOCÊ mm:ss-mm:ss] ...` nas falas suas.

**Se falhar:**
- Verificar permissão de microfone no Windows.
- Confirmar `CAPTURAR_MIC=True` e perfil existente.
- Ajustar `LIMIAR_IDENTIFICACAO_VOZ` (0.65–0.80) via `config_user.json`.

### Gate final v1.2 — `AC-FINAL`

```bash
python -m pytest tests/ -v --tb=short
python scripts/verificar_fase.py --fase all
```

Inclui F0–F7. Só declarar v1.2 completa com **ambos** F6 e F7 verdes.

---

## Procedimento de correção (qualquer fase)

```
1. Capturar output completo do gate falho
2. Invocar superpowers:systematic-debugging
3. Formular hipótese → teste mínimo que reproduz
4. Fix cirúrgico (escopo da fase atual)
5. Re-rodar gate da fase
6. Se 3 falhas consecutivas no mesmo AC → escalar: revisar spec/tasks
7. Registrar desvio em docs/sdd/v1.2/CHANGELOG.md (criar na F6)
```

---

## Gestão de risco

| Risco | Mitigação |
|-------|-----------|
| pystray difícil de testar | Mock `Icon` em testes; teste manual checklist |
| GPU indisponível em CI | `DEVICE_WHISPER=cpu` em conftest |
| Token quebra bookmark | Persistir token em `config_user.json` sessão |
| Thread Flask zombie | `daemon=True` + flag `_assistente_rodando` + cleanup on exit |

---

## Execução recomendada (superpowers)

**Opção A (recomendada):** `subagent-driven-development` — um subagent por tarefa `T-*`, review entre tarefas.

**Opção B:** `executing-plans` — executar fase completa inline com checkpoint no gate.

Ao concluir v1.2: `finishing-a-development-branch` + `requesting-code-review`.