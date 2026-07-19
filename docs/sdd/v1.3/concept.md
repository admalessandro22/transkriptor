# Concept — Transkriptor v1.3 "Nomes, Ollama e Atalho Global"

## Contexto

O Transkriptor v1.2.1 está funcional: bandeja estável, detecção de Meet com debounce,
transcrição offline (faster-whisper), diarização ECAPA, criptografia em repouso
(AES-GCM + DPAPI), assistente Flask + Ollama e ponte WebSocket com extensão Chrome.
A suíte tem **170 testes, todos verdes** (baseline auditado em 2026-07-19).

## Problemas encontrados na auditoria (2026-07-19)

### A. Bloqueadores de produto

| ID | Problema | Evidência |
|----|----------|-----------|
| A1 | **Contexto do Ollama estoura silenciosamente.** `MAX_CHARS_TRANSCRICAO=80000` (~20k tokens) é enviado sem `options.num_ctx`; o Ollama trunca no default (2k–4k tokens) e o modelo responde ignorando a maior parte da reunião, sem aviso. | `assistente.py:850-854` (payload sem `options`) |
| A2 | **Não existe atalho de teclado no código.** A "ativação por Ctrl+Alt" vem da propriedade *Shortcut key* do atalho `.lnk` do Windows — que **só aceita combinações Ctrl+Alt+tecla**. Ctrl+Espaço é impossível via `.lnk`; exige `RegisterHotKey` nativo no app. | grep por hotkey/keyboard: zero ocorrências; `criar_atalho_desktop.ps1` não define `.Hotkey` |
| A3 | **Nomes do Meet frágeis.** A extensão depende de classes ofuscadas do Meet (`.NWpY1d`, `.zs7s8d`, `.kssMZb`) que quebram a cada release do Google; correlação por janela de 1.5s atribui nome errado quando duas pessoas falam próximas. As legendas do Meet já trazem **nome + texto juntos** e não são capturadas. | `extension/meet/content.js:51-57`, `correlacionador.py:13-31` |
| A4 | **Watchdog pode reiniciar thread com arquivo fechado.** `_processar()` fecha `_arq`/`_wav` no `finally`; se a thread morre e o watchdog a reinicia, `self._arq is None` e o texto para de ser gravado silenciosamente. | `transcricao_core.py:235-245` + `watchdog.py:66-75` |
| A5 | **Projeto não é repositório git.** Todo o método SDD/commits do AGENTS.md é inexequível; sem histórico, sem rollback. Lixo versionável na raiz: `_a.txt`, `_srv.txt`, `_srv2.txt`, `terminals/`, `agent-tools/`, `transkriptor.log`. | ambiente: `Is a git repository: false` |

### B. Instalador (`instalar.bat`)

| ID | Problema |
|----|----------|
| B1 | Não verifica versão do Python (projeto exige 3.12+); falha tarde e de forma confusa. |
| B2 | Instala no Python global — sem venv; conflita com outros projetos e dificulta desinstalação. |
| B3 | Tenta CUDA cu128 sempre, mesmo sem GPU NVIDIA (~2.5 GB de download inútil antes do fallback). Não detecta GPU (`nvidia-smi`). |
| B4 | Não faz warm-up dos modelos (Whisper + ECAPA baixam na **primeira reunião**, atrasando a transcrição em minutos). |
| B5 | Não detecta Ollama nem sugere/puxa um modelo recomendado — mas o assistente depende dele. |
| B6 | Não existe desinstalador nem caminho de atualização. |
| B7 | Versões divergentes: instalador diz "1.2.1", `pyproject.toml` diz "1.2.0", bandeja/tooltip dizem "1.1". |

### C. Qualidade e coerência do código

| ID | Problema |
|----|----------|
| C1 | `_ler_trecho_wav` duplicada em `transcricao_core.py:298` e `diarizador.py:78` — viola a própria regra "não duplicar lógica" do AGENTS.md. |
| C2 | Leitura/escrita de `config_user.json` duplicada (`transkriptor.pyw` e `crypto_storage.py`) e **sem lock** — escrita concorrente (toggle do menu vs. geração de chave DPAPI) pode corromper o JSON que guarda a chave mestra. |
| C3 | `transkriptor.pyw` é um god-object de ~890 linhas (UI + config + startup + voz + bridge + assistente). |
| C4 | `assistente.py` embute ~650 linhas de HTML/CSS/JS numa string Python; impossível lintar/testar o front. |
| C5 | Token do assistente trafega em `?token=` na URL (fica no histórico do navegador). Cookie de sessão é mais seguro. |
| C6 | `reforcar_rotulo_por_mic` marca como VOCÊ qualquer segmento com energia no mic — com alto-falantes (sem fone), o eco da reunião rotula outros falantes como VOCÊ. |
| C7 | `transcricao_contem_voce()` usa a constante `ROTULO_USUARIO` ("VOCÊ") e ignora `rotulo_usuario` customizado do usuário — badge "com sua voz" some se o usuário renomeou o rótulo. |
| C8 | Diarização clusteriza embeddings por segmento inteiro do Whisper (até 25s); segmentos com dois falantes recebem um rótulo só. Limiar 0.25 fixo, não configurável. |
| C9 | `win10toast` é fallback no `notificador.py` mas não está no `requirements.txt` (fallback morto). |
| C10 | `_EXCLUIR` do detector descarta reuniões cujo nome da sala contenha "tutorial", "ajuda", "novidades" etc. (falso negativo). |
| C11 | AGENTS.md aponta v1.2 como versão em execução; v1.2.1 já foi entregue (ponteiro obsoleto). |
| C12 | Modelo Whisper fixo em `base` — qualidade limitada para pt-BR; não há opção no menu da bandeja. |

## Decisões do usuário (2026-07-19)

| Decisão | Escolha |
|---------|---------|
| Retenção do áudio bruto | **Manter WAV por 7 dias** após a reunião (permite retranscrever); limpeza automática depois |
| Pausa da detecção | **Mantida, com confirmação e aviso persistente** de "NÃO está gravando"; pausa não persiste entre sessões |
| Formato das transcrições | **Criptografado (.tkpt)** continua sendo o padrão; áudio retido também é criptografado ao finalizar |
| Modelo Whisper | **Auto por hardware.** Detectado: GTX 1650 4 GB + i7-9750H + 32 GB RAM → `medium` em CUDA/int8_float16; fallback `small`/int8 em CPU |

**Requisito central adicionado:** *toda reunião detectada deve resultar em transcrição
gravada localmente* — falha de modelo, de diarização ou de qualquer pós-processamento
nunca pode causar perda da reunião (o áudio é a fonte de verdade recuperável).

## Objetivo da v1.3

1. **Gravação local garantida**: nenhuma reunião se perde — áudio WAV sempre salvo
   (retenção 7 dias, criptografado), retranscrição pelo menu, pausa com aviso explícito,
   falha de Whisper/diarização nunca descarta o áudio.
2. **Assistente Ollama confiável**: contexto dimensionado ao modelo (`num_ctx`), aviso honesto
   de truncagem, map-reduce para reuniões longas, timeouts.
3. **Atalho global nativo Ctrl+Espaço** (configurável) para iniciar/parar transcrição manual,
   via `RegisterHotKey` — substituindo qualquer dependência de hotkey de `.lnk` (Ctrl+Alt).
4. **Nomes das vozes robustos**: captura das legendas do Meet (nome+texto), seletores com
   fallback, correlação menos ambígua.
5. **Qualidade de transcrição por hardware**: modelo Whisper `auto` (GPU → `medium` CUDA;
   CPU → `small`), ajustável no menu.
6. **Instalador de verdade**: venv, checagem de Python/GPU/Ollama, warm-up de modelos,
   desinstalador, versão única.
7. **Dívida técnica**: git, dedupe, lock de config, split do god-object, front separado.

## Fora de escopo

- Suporte a outras plataformas de reunião (Zoom/Teams).
- Empacotamento em .exe (PyInstaller) — candidato à v1.4.
- Diarização com pyannote (licença/token HF) — mantém ECAPA + melhorias incrementais.

## Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Ctrl+Espaço conflita com IME (idiomas asiáticos) e autocomplete de IDEs | Combo configurável em `config_user.json`; se `RegisterHotKey` falhar (código de erro 1409 — já registrado), notificar e seguir sem hotkey |
| Seletores do Meet mudam de novo | Estratégia em camadas: legendas (DOM semiestável) → atributos `data-*` → classes; testes de parsing com fixtures HTML |
| `num_ctx` alto estoura RAM/VRAM do usuário | Detectar tamanho do modelo via `/api/show` e limitar; fallback map-reduce |
