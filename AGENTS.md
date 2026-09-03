# AGENTS.md — Transkriptor

Guia universal para agentes de IA (Cursor, Grok, Claude Code, Codex) neste repositório.

## Produto

**Transkriptor** — app de bandeja Windows que detecta Google Meet, transcreve offline (Whisper),
diariza falantes e oferece assistente local via Ollama.

Versão do produto: `config.VERSAO` (fonte única; não hardcodar em outros arquivos).

## Método de trabalho

Este projeto usa **Spec-Driven Development (SDD)** + **Superpowers**.

### Ordem obrigatória

1. Ler `docs/sdd/v1.6/plan.md` → plano fechado, ordem F11.A–F11.H, gates.
2. Ler `docs/sdd/v1.6/concept.md` → visão e escopo.
3. Ler `docs/sdd/v1.6/spec.md` → requisitos `FR-*`, `SEC-*`, `UX-*`.
4. Ler `docs/sdd/v1.6/tasks.md` → tarefa atual.
5. Executar **uma tarefa por vez** de `docs/sdd/v1.5/tasks.md`.
6. **Antes de codar:** invocar skill `superpowers:test-driven-development`.
7. **Antes de declarar fase concluída:** invocar skill `superpowers:verification-before-completion`.
8. **Se testes falharem:** invocar skill `superpowers:systematic-debugging` → corrigir → re-rodar gate.

### Skills Superpowers (projeto)

Instaladas em `.grok/skills/superpowers/`. Principais:

| Skill | Quando usar |
|-------|-------------|
| `using-superpowers` | Início de toda sessão |
| `writing-plans` | Antes de planos multi-etapa |
| `test-driven-development` | Antes de qualquer código de feature/fix |
| `executing-plans` | Executar plano fase a fase |
| `subagent-driven-development` | Tarefas independentes em paralelo |
| `verification-before-completion` | Antes de marcar tarefa/fase como done |
| `systematic-debugging` | Quando gate de fase falha |
| `requesting-code-review` | Ao fechar uma fase |

### Regras de código

- Python 3.12+, UTF-8, `config.py` para constantes.
- Não duplicar lógica — `transcricao_core.Transcritor` é o núcleo.
- Flask do assistente: **sempre** `host="127.0.0.1"`.
- Transcrições são dados sensíveis — validar paths, escapar HTML, não logar conteúdo.
- Commits em português, imperativo: `fix: corrige ordem de startup do assistente`.
- Uma tarefa (`T-*`) = um commit (ou stack pequeno relacionado).

### Testes

```bash
python -m pytest tests/ -v
python -m pytest tests/ -v --tb=short -x   # parar no primeiro erro
```

Gate de fase: ver `docs/sdd/v1.3/plan.md` § "Gates de verificação".

### Gate de reunião real (NFR-10.C2) — obrigatório ao mexer em captura

```bash
python scripts/gate_reuniao_real.py --segundos 25    # rápido
python scripts/gate_reuniao_real.py --segundos 600   # gate longo
```

Toca fala pelo alto-falante, captura pelo loopback com o `Transcritor` real,
encerra, enfileira e roda o Whisper de verdade até sair um `.txt` legível.
**Suíte verde não substitui este gate:** em 2026-08-07 o produto ficou incapaz
de gravar um único frame com 380 testes passando.

### Travamento da bandeja (regressão 2026-08-07)

O app ficou três dias vivo na bandeja sem gravar nada e sem uma linha no log:
`Transcritor.start()` rodava sob `self._lock` e chama `on_status`, que é
`_status`, que pedia o mesmo lock não reentrante. Regras que não podem regredir:

- **Nada que dispare callback roda sob `self._lock`** — `tests/test_lock_sem_callback.py`
  lê o código e reprova o padrão. `_status` nunca pede o lock.
- **Dublê de `Transcritor` chama `on_status` no `start()`/`stop()`**, como o real
  — `tests/test_dubles_fieis.py`. Dublê mudo não exercita o caminho que travou.
- **Toda falha vira sinal visível**: `VigiaMonitor` alarma se o loop do monitor
  parar de bater; o portão de consentimento expira; mensagens de `Reunião`/
  `Gravação` não são censuradas pelo sanitizador.
- **A suíte não escreve em `transkriptor.log`** (fixture `log_de_teste`). Nunca
  fazer `import transkriptor` num teste: isso carrega a bandeja inteira na
  coleta e reinstala o handler de produção.

### Identificação de voz (`VOCÊ`)

Loopback sozinho **não** captura sua voz na maioria dos Meets. O produto usa:
cadastro de perfil (mic 20s) + gravação paralela do mic + matching ECAPA na diarização.
Ver `docs/sdd/v1.3/concept.md`.

### Versões SDD

| Versão | Pasta | Status |
|--------|-------|--------|
| 1.1 | `docs/sdd/` (raiz legado) | Implementado |
| 1.2 | `docs/sdd/v1.2/` | Legado (auditoria) |
| 1.2.1 | `docs/sdd/v1.2.1/` | Legado (estabilidade bandeja) |
| 1.3 | `docs/sdd/v1.3/` | Legado (implementado) |
| 1.4 | `docs/sdd/v1.4/` | Legado (implementado) |
| 1.5 | `docs/sdd/v1.5/` | Legado (implementado) |
| 1.6 | `docs/sdd/v1.6/` | **Em execução (fonte de verdade)** |

### Detecção de reunião (v1.4)

Nunca voltar a depender de **uma** fonte só. `deteccao_reuniao.DetectorReuniao`
combina título de janela, microfone em uso (`monitor_microfone.py`) e ponte da
extensão. Regras que não podem regredir:

- O título da janela só revela a **aba em primeiro plano** — por isso qualquer
  fonte mantém a reunião viva.
- O formato do título do Meet **muda**: hoje é `Meet – abc-defg-hij`. Ao mexer no
  regex, manter os dois formatos e os testes parametrizados.
- `Meet - Google Chrome` é a aba do Meet **fora** de chamada, não reunião. O que
  vem depois de `Meet – ` não pode ser só o nome do navegador.
- **Zoom não se detecta por texto.** O título muda com idioma e versão
  (`Zoom Meeting`, `Reunião Zoom`, `Zoom Workplace`). `detector_zoom` usa classe
  de janela e microfone do `zoom.exe` corroborado. Se uma versão nova mudar a
  classe, o Diagnóstico da bandeja mostra título+classe para atualizar a lista.
- Antes de mexer em captura de áudio, rodar `tests/test_diagnostico.py` — o gate
  de compatibilidade `soundcard`×`numpy` mora lá.

### COM e as threads de áudio (regressão 2026-08-10)

`soundcard` inicializa COM **uma única vez**, num singleton de módulo
(`_com = _COMLibrary()`), na thread que importar primeiro; o `__del__` dele
chama `CoUninitialize()`. Num app com várias threads isso derruba o MTA do
processo e a captura falha com `Error 0x800401f0` (`CO_E_NOTINITIALIZED`) —
reunião gravada em branco, com o mesmo sintoma de um travamento.

Toda thread que fala com `soundcard` **tem** de rodar dentro de
`com_audio.com_inicializada()`. `tests/test_com_audio.py` reproduz a falha em
subprocesso (derrubar o MTA contamina o processo inteiro) e cobra o contexto
por AST em `_capturar` e `_capturar_mic`.
