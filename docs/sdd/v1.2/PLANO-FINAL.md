# Plano Final — Transkriptor v1.2

**Status:** FECHADO — pronto para execução  
**Data:** 2026-07-08  
**Método:** SDD + TDD (Superpowers)  
**Estimativa total:** 32–42h  
**Artefatos:** `concept.md` · `spec.md` · `tasks.md` · `docs/superpowers/plans/2026-07-08-...md`

---

## 1. Visão da entrega

Ao concluir v1.2, o Transkriptor será:

- **Confiável** — bugs P0 corrigidos, testes automatizados, gates por fase
- **Seguro** — transcrições criptografadas, legíveis só pelo app + assistente autenticado
- **Identificável** — rotula `VOCÊ` (mic + perfil) e nomes do Meet (extensão estilo Tactiq)
- **Configurável** — menu de bandeja com todas as opções abaixo
- **Local** — sem nuvem obrigatória (Ollama e Whisper continuam offline)

---

## 2. Ordem lógica de desenvolvimento

A ordem abaixo respeita **dependências técnicas**: cada fase só começa quando a anterior passou no gate.

```
F0  Fundação QA (pytest)
 └─► F1  Correções críticas (assistente, API)
      └─► F2  Engenharia (mutex, logs, GPU, ícones)
           └─► F3  Criptografia em repouso  ◄── antes de dados sensíveis (voz, nomes)
                └─► F4  Menu de opções + UX bandeja
                     ├─► F5  UX assistente (lê via crypto)
                     └─► F6  Segurança API (token sessão)
                          └─► F7  Identificação VOCÊ (mic + perfil)
                               └─► F8  Nomes no Meet (extensão + legendas CC)
                                    └─► F9  Manutenção + GATE FINAL
```

**Por que criptografia na F3 (e não no fim)?**  
Perfis de voz, legendas com nomes e transcrições diarizadas são dados sensíveis. Criptografar **antes** das fases 7–8 evita migração em massa e vazamento de plaintext.

**Por que F8 por último (features)?**  
Depende de WebSocket, extensão Chrome e opcionalmente F7 para prioridade de rótulos.

---

## 3. Menu de opções do aplicativo (bandeja)

Todas as opções abaixo ficam no menu `pystray`, persistidas em `config_user.json` quando aplicável.

### 3.1 Núcleo (já existe v1.1 — manter)

| Item | Tipo | Descrição |
|------|------|-----------|
| Status dinâmico | label | Aguardando / Transcrevendo / Separando vozes / Pausado / Erro |
| Abrir pasta de transcrições | ação | Explorer na pasta `transcricoes/` |
| Abrir assistente | ação | Flask local + navegador |
| Pausar / retomar detecção Meet | toggle | Debounce Meet on/off |
| Separar vozes (diarização) | toggle | `_diarizado` on/off |
| Iniciar com o Windows | toggle | Atalho shell:startup |
| Sair | ação | Com confirmação se gravando (F4) |

### 3.2 Novas opções v1.2

| Item | Fase | Tipo | Default | Descrição |
|------|------|------|---------|-----------|
| **Criptografar transcrições** | F3 | toggle | `true` | Arquivos ilegíveis fora do app |
| Abrir log | F4 | ação | — | `Transkriptor.log` |
| Transcrição manual | F4 | ação | — | Grava sem detectar Meet |
| **Capturar microfone** | F7 | toggle | `true` | WAV `_mic.wav` para VOCÊ |
| **Identificar minha voz (VOCÊ)** | F7 | toggle | `true` se perfil | Matching ECAPA |
| Cadastrar minha voz | F7 | ação | — | Wizard 20s |
| Apagar perfil de voz | F7 | ação | — | Remove embedding |
| **Nomes via legendas Meet** | F8 | toggle | `false` | Modo Tactiq (extensão + CC) |
| Instalar extensão Chrome | F8 | ação | — | Abre pasta `extension/` + instruções |
| Renomear falante… | F8 | submenu | — | FALANTE_XX → nome (banco local) |

### 3.3 Prioridade de rótulos na diarização (F7+F8)

```
Nome Meet (legendas CC)  >  VOCÊ (perfil mic)  >  Nome cadastrado (vozes_conhecidas)  >  FALANTE_XX
```

---

## 4. Fases detalhadas

### F0 — Fundação QA · 2h · `AC-F0`

| Entregável | Teste |
|------------|-------|
| `pyproject.toml`, `requirements-dev.txt` | `pytest --version` |
| `tests/conftest.py` | fixtures OK |
| `tests/test_detector_meet.py` | ≥8 testes verdes |
| `scripts/verificar_fase.py` | `--fase 0` exit 0 |

```bash
python -m pip install -r requirements-dev.txt
python scripts/verificar_fase.py --fase 0
```

---

### F1 — Correções críticas · 3h · `AC-F1`

| ID | Entrega |
|----|---------|
| FR-1.1–1.2 | Assistente: thread Flask → health check → browser |
| FR-1.3–1.4 | `caminho_transcricao_seguro()` + 403 |
| FR-1.5 | Anti-XSS no select |

```bash
python scripts/verificar_fase.py --fase 1
# Manual: abrir assistente 3× seguidas — 3/3 OK
```

---

### F2 — Engenharia · 4h · `AC-F2`

| ID | Entrega |
|----|---------|
| FR-2.1–2.2 | Ícone erro (vermelho) + pausado (cinza) |
| FR-2.3–2.4 | `DEVICE_WHISPER=auto` |
| FR-2.5 | `instalar.bat` pythonw dinâmico |
| FR-2.6 | Mutex instância única |
| FR-2.7–2.9 | Log rotation, limpeza código |

```bash
python scripts/verificar_fase.py --fase 2
```

---

### F3 — Criptografia em repouso · 5h · `AC-F3`

**Objetivo:** Transcrições abertas **somente** pelo Transkriptor e assistente autenticado.

#### Design técnico

| Aspecto | Decisão |
|---------|---------|
| Algoritmo | **AES-256-GCM** (`cryptography` Fernet ou AESGCM) |
| Formato arquivo | Extensão `.tkpt` (ou `.txt.tkpt`); magic header `TKPT1` |
| Chave mestra | Gerada na 1ª execução; protegida com **Windows DPAPI** (`CryptProtectData`) → `config_user.json` campo `chave_dpapi` |
| Passphrase opcional | Futuro v1.3; v1.2 só DPAPI máquina+usuário Windows |
| O que criptografa | `transcricao_*.tkpt`, `*_diarizado.tkpt`, `perfil_usuario.enc`, `vozes_conhecidas.enc` |
| WAV temporário | Não criptografado; apagado após diarização |
| Migração | Na 1ª ativação: `.txt` legados → `.tkpt`; backup `.txt.bak` opcional |
| Leitura externa | Notepad/Explorer mostra binário ilegível |
| API assistente | `crypto_storage.ler(nome)` — único caminho de leitura |

#### Módulo `crypto_storage.py`

```python
# Interfaces principais
def criptografar_bytes(plano: bytes) -> bytes: ...
def descriptografar_bytes(cifrado: bytes) -> bytes: ...
def salvar_transcricao(caminho_logico, texto: str) -> None: ...
def ler_transcricao(nome_arquivo: str) -> str: ...
def migrar_txt_legacy(pasta: str) -> int: ...  # retorna quantidade migrada
def chave_disponivel() -> bool: ...
```

#### Requisitos (spec FR-3.*)

| ID | Requisito |
|----|-----------|
| FR-3.1 | Módulo `crypto_storage.py` com AES-256-GCM + DPAPI |
| FR-3.2 | `Transcritor` grava via `salvar_transcricao`; nunca plaintext em disco se toggle on |
| FR-3.3 | `assistente.py` lê só via `ler_transcricao` |
| FR-3.4 | Toggle menu "Criptografar transcrições" (default on) |
| FR-3.5 | Migração automática de `.txt` existentes na ativação |
| FR-3.6 | `abrir_pasta` continua funcionando; arquivos `.tkpt` não legíveis externamente |
| FR-3.7 | Teste: bytes aleatórios round-trip; arquivo em disco não contém plaintext da frase-teste |

| SEC-8 | Chave nunca em log; DPAPI scope = usuário atual |
| SEC-9 | Descriptografia falha → mensagem "Abra pelo Transkriptor" (sem dump de chave) |

```bash
python scripts/verificar_fase.py --fase 3
# Manual: abrir .tkpt no Bloco de notas → lixo/binário
# Manual: assistente lista e analisa transcrição OK
```

---

### F4 — Menu de opções + UX bandeja · 4h · `AC-F4`

Consolida **seção 3** no menu real + melhorias UX.

| ID | Entrega |
|----|---------|
| FR-4.1 | Toast ao vivo (60 chars, Meet não focado) |
| FR-4.2 | Itens: log, transcrição manual |
| FR-4.3 | Confirmar saída se gravando |
| FR-4.4 | Progresso diarização N/total |
| FR-4.5 | Submenu "Opções" com toggles agrupados |
| FR-4.6 | `config_user.json` schema versionado (`versao_config: 2`) |

```bash
python scripts/verificar_fase.py --fase 4
```

---

### F5 — UX assistente · 4h · `AC-F5`

| ID | Entrega |
|----|---------|
| FR-5.1 | Timer "O modelo está pensando..." após 15s |
| FR-5.2 | Barra progresso indeterminada |
| FR-5.3 | Drawer mobile + copiar + tamanho_kb |
| FR-5.4 | Lista transcrições `.tkpt` com preview via decrypt |

```bash
python scripts/verificar_fase.py --fase 5
```

---

### F6 — Segurança API · 3h · `AC-F6`

| ID | Entrega |
|----|---------|
| FR-6.1 | Token sessão `X-Transkriptor-Token` + `?token=` na URL |
| FR-6.2 | Meet visível (opcional) |
| FR-6.3 | Truncar contexto Ollama 80k chars |

```bash
python scripts/verificar_fase.py --fase 6
```

---

### F7 — Identificação VOCÊ · 6h · `AC-F7`

| ID | Entrega |
|----|---------|
| FR-7.1–7.10 | `identificador_voz.py`, mic paralelo, rótulo VOCÊ |
| FR-7.11 | Perfil salvo **criptografado** (`perfil_usuario.enc`) |

```bash
python scripts/verificar_fase.py --fase 7
# Manual: cadastrar voz → Meet teste → [VOCÊ mm:ss-mm:ss] no diarizado
```

---

### F8 — Nomes no Meet (estilo Tactiq) · 8h · `AC-F8`

| ID | Entrega |
|----|---------|
| FR-8.1–8.2 | Extensão Chrome + WebSocket `127.0.0.1:5051` |
| FR-8.7 | Lê **Closed Captions** do DOM (nome + texto) |
| FR-8.8 | Aviso se CC desligado |
| FR-8.3–8.5 | `correlacionador.py` + banco vozes conhecidas |

Estrutura extensão:

```
extension/Transkriptor-meet/
  manifest.json
  content.js      # MutationObserver nas legendas CC
  background.js   # WebSocket → localhost:5051
```

```bash
python scripts/verificar_fase.py --fase 8
# Manual: CC on → 2 participantes → nomes no .tkpt diarizado
```

---

### F9 — Manutenção + encerramento · 2h · `AC-FINAL`

| ID | Entrega |
|----|---------|
| FR-9.1 | `.gitignore` completo |
| FR-9.2 | `docs/VERIFICACAO.md` (gates F0–F9) |
| FR-9.3 | `CHANGELOG.md` v1.2 |
| FR-9.4 | `requirements.txt` + `cryptography>=42` |

```bash
python -m pytest tests/ -v --tb=short
python scripts/verificar_fase.py --fase all
```

**v1.2 só fecha com `AC-FINAL` verde.**

---

## 5. Mapa de fases → arquivos principais

| Fase | Arquivos novos/modificados |
|------|---------------------------|
| F0 | `pyproject.toml`, `tests/*`, `scripts/verificar_fase.py` |
| F1 | `assistente.py`, `Transkriptor.pyw` |
| F2 | `config.py`, `Transkriptor.pyw`, `instalar.bat` |
| F3 | **`crypto_storage.py`**, `transcricao_core.py`, `assistente.py` |
| F4 | `Transkriptor.pyw`, `config_user.json` |
| F5 | `assistente.py` (HTML/JS) |
| F6 | `assistente.py`, `detector_meet.py` |
| F7 | **`identificador_voz.py`**, `diarizador.py`, `transcricao_core.py` |
| F8 | **`meet_bridge.py`**, **`correlacionador.py`**, `extension/` |
| F9 | `.gitignore`, `docs/VERIFICACAO.md` |

---

## 6. Dependências Python novas

```
cryptography>=42.0    # F3 criptografia
```

(já existentes: faster-whisper, speechbrain, flask, pystray, …)

---

## 7. Critérios de aceite globais v1.2

- [ ] `pytest` 100% verde (`verificar_fase.py --fase all`)
- [ ] Assistente abre 10/10 na 1ª tentativa
- [ ] Path traversal → 403
- [ ] `.tkpt` ilegível no Bloco de notas; legível no assistente
- [ ] Toggle criptografia off → grava `.txt` legado (retrocompat)
- [ ] Perfil voz + mic → linhas `VOCÊ` no diarizado
- [ ] Extensão + CC on → nomes reais no diarizado
- [ ] Mutex bloqueia 2ª instância
- [ ] Ícone vermelho em erro crítico

---

## 8. Execução (Superpowers)

1. Skill `Transkriptor-sdd` → tarefa `T-F*` em `tasks.md`
2. Skill `test-driven-development` antes de cada tarefa
3. Gate da fase → falhou? `systematic-debugging` → re-gate
4. Fase OK → `verification-before-completion`
5. Plano TDD detalhado: `docs/superpowers/plans/2026-07-08-Transkriptor-v1.2-audit-remediation.md` (+ addendum F3 crypto, F8)

**Modo recomendado:** `subagent-driven-development` (1 subagent por tarefa).

---

## 9. Fora de escopo v1.2 (v1.3+)

- Passphrase user-facing para chave
- Suporte Teams/Zoom nativo
- Bot participante no Meet
- CI GitHub Actions
- Instalador MSI
- Markdown rendering nas respostas IA (FR-5.7 opcional baixa prioridade)

---

## 10. Resumo executivo

| # | Fase | Horas | Entrega chave |
|---|------|-------|---------------|
| 0 | QA | 2h | pytest + gates |
| 1 | P0 | 3h | Assistente funciona |
| 2 | Eng | 4h | Confiável 24/7 |
| 3 | **Crypto** | 5h | **`.tkpt` só no app** |
| 4 | Bandeja | 4h | **Menu opções completo** |
| 5 | Assistente UX | 4h | UX-05 completo |
| 6 | API seg | 3h | Token sessão |
| 7 | VOCÊ | 6h | Sua voz identificada |
| 8 | Meet nomes | 8h | Extensão Tactiq-like |
| 9 | Fechar | 2h | Docs + GATE FINAL |
| | **Total** | **~41h** | **Transkriptor v1.2** |

**Plano fechado.** Próximo passo: executar **F0** (`T-F0-01`).