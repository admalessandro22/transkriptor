# Spec — Transkriptor v1.4

Requisitos verificáveis. Cada `FR/NFR/UX` tem ao menos um teste automatizado
citando o ID em docstring ou comentário.

Contexto e causas raiz: `concept.md`. Ordem de execução e gates: `plan.md`.

## F9.A — Captura de áudio confiável (causa raiz 1)

- **FR-9.A1** `requirements.txt` exige `soundcard>=0.4.6` e `numpy>=1.24,<3`.
  Versões de `soundcard` anteriores a 0.4.6 usam `numpy.fromstring`, removida no
  numpy 2.0, e fazem **toda** captura levantar `ValueError`.
  *Teste:* `test_diagnostico.py::test_soundcard_instalado_e_compativel_com_numpy`
  falha o gate se a combinação instalada for incompatível.
- **FR-9.A2** `audio_utils.diagnosticar_captura(bloco, erro=None)` é função pura e
  classifica o resultado de uma tentativa de captura em
  `{ok, motivo, rms, frames}`. Exceção → `ok=False` com o motivo legível;
  bloco vazio → `ok=False`; silêncio (RMS 0 com quadros) → `ok=True`.
- **FR-9.A3** `audio_utils.testar_loopback()` e `testar_microfone()` gravam meio
  segundo real e **nunca levantam**: devolvem o dict de FR-9.A2 acrescido de
  `dispositivo`.
- **FR-9.A4** Na inicialização, o app roda `testar_loopback()` em thread própria.
  Falha vira erro crítico visível (ícone de erro + toast apontando o
  Diagnóstico), nunca silêncio no log.
- **NFR-9.A1** Uma reunião real gravada produz WAV com quadros: um `.wav.enc` de
  77 bytes (só cabeçalho) é evidência de regressão desta fase.

## F9.B — Detecção multi-fonte (causa raiz 2)

- **FR-9.B1** `deteccao_reuniao.DetectorReuniao` combina fontes independentes por
  OR. **Qualquer** fonte ativa mantém a reunião viva; o fim só é declarado após
  `CONFIRMACAO_FIM_REUNIAO` ciclos sem **nenhuma** fonte.
- **FR-9.B2** Debounce assimétrico: início por fonte **forte** em
  `CONFIRMACAO_INICIO_MEET` ciclos (2 = 10 s); início só por fonte **fraca** em
  `CONFIRMACAO_INICIO_FRACA` ciclos (4 = 20 s); fim em
  `CONFIRMACAO_FIM_REUNIAO` ciclos (6 = 30 s). O fim é sempre mais lento que o
  início.
- **FR-9.B3** `detector_meet.classificar_titulo(titulo)` devolve `"forte"`,
  `"nomeado"` ou `""`. Reconhece, como **forte**:
  `Meet – abc-defg-hij` (hífen, travessão curto e longo), `^Meet – <texto>`,
  `meet.google.com/<codigo>`, `<codigo> - Google Meet` e reunião do Zoom
  (`Zoom Meeting` / `Reunião do Zoom`). Reconhece como **nomeado** o formato
  legado `<sala> - Google Meet`.
- **FR-9.B4** A lista de exclusão (pesquisa, tutorial, ajuda, login…) se aplica
  **somente** ao casamento nomeado. Uma sala chamada "Ajuda ao cliente" continua
  sendo reunião.
- **FR-9.B5** `Google Meet - Google Chrome` (página inicial, sem sala) e
  `Zoom Workplace` (app fora de chamada) **não** são reunião.
- **FR-9.B6** `FonteMicrofone` consulta
  `HKCU\...\CapabilityAccessManager\ConsentStore\microphone`: subchave com
  `LastUsedTimeStop == 0` significa microfone em uso agora. Só executáveis de
  `monitor_microfone.APPS_CONFERENCIA` contam — ditado por voz (WisprFlow,
  digitação por voz) nunca vira reunião. É fonte **fraca**.
- **FR-9.B7** `FontePonte` lê `MeetBridge.reuniao_ativa()`, alimentado pelo
  heartbeat `{tipo:"reuniao", ativa: bool}` da extensão. É fonte **forte** e
  expira em 20 s sem heartbeat (a aba pode ser fechada sem avisar).
- **FR-9.B8** A extensão envia o heartbeat a cada 5 s e `ativa:false` no
  `beforeunload`; `emChamada()` exige URL com código de sala **e** controles da
  chamada no DOM (sair da chamada / microfone), para não disparar na tela inicial.
- **FR-9.B9** A ponte WebSocket sobe **sempre**, não só com "Identificar nomes do
  Meet" ligado. Falha ao subir (porta ocupada) não impede a bandeja: título e
  microfone seguem detectando.
- **FR-9.B10** Qualquer fonte que levante exceção é tratada como inativa e
  registrada em debug; o monitor nunca cai por causa de uma fonte.
- **UX-9.B1** O item de status do menu informa o que o detector vê agora
  ("Aguardando reunião — sinal de: microfone" / "nenhuma reunião à vista") e, ao
  gravar, quais fontes confirmaram a reunião.

## F9.C — Autodiagnóstico e observabilidade

- **FR-9.C1** Menu da bandeja tem **"Diagnóstico (por que não está gravando?)"**,
  que roda em thread própria, salva relatório `.txt` ao lado do log e abre no
  editor padrão.
- **FR-9.C2** O relatório cobre: ambiente (versão, Python, Windows, disco),
  compatibilidade `soundcard`×`numpy`, autoteste real de loopback e microfone,
  leitura instantânea de **cada** fonte de detecção e o modelo Whisper resolvido.
  Cada item é `OK`, `AVISO` ou `ERRO`, com resumo final de contagem.
- **FR-9.C3** `diagnostico.resumir(itens) -> (erros, avisos)` alimenta o toast
  final.
- **FR-9.C4** O monitor registra heartbeat no log a cada
  `HEARTBEAT_MONITOR_CICLOS` ciclos (~10 min) com estado da reunião, fontes
  ativas e se está gravando — prova de vida mesmo sem mudança de estado.

## F9.D — Ciclo de vida e concorrência

- **FR-9.D1** `adquirir_lock(caminho, usar_mutex_nomeado=True)` usa mutex nomeado
  do Windows (`Global\TranskriptorInstanciaUnica`) como fonte da verdade. O
  kernel libera o mutex quando o processo morre, inclusive se for morto à força;
  concedido o mutex, um arquivo de lock remanescente é removido como lixo.
  Elimina o travamento permanente por PID reciclado.
- **FR-9.D2** Iniciar e parar a transcrição rodam **fora** da thread do monitor
  (`_em_thread`), para que carregar o Whisper e finalizar a diarização não
  cequem a detecção.
- **FR-9.D3** `_iniciar_transcricao` tem portão atômico (`_iniciando` sob lock):
  monitor e menu manual não abrem duas capturas concorrentes.
- **FR-9.D4** O aviso de gravação (FR-2.9) é precedido de toast e usa
  `MessageBoxTimeoutW` com `argtypes`/`restype` declarados. O texto explica as
  duas opções e o comportamento do timeout.
- **FR-9.D5** Nova opção de menu **"Perguntar antes de gravar"**, persistida em
  `config_user.json` (`perguntar_antes_de_gravar`, padrão `true`). Desligada, a
  gravação automática não interrompe o usuário.

## F9.E — Correções de qualidade

- **FR-9.E1** `VRAM_MIN_MEDIUM_GB = 3.8`. Placas "de 4 GB" reportam 3.99969 GiB
  (GTX 1650 = 4294639616 bytes); com o limiar em 4.0 exatos o hardware de
  referência da spec v1.3 caía sempre em `small`/CPU.
- **NFR-9.E1** `python -m pytest tests/ -q` 100% verde.
- **NFR-9.E2** Nenhum arquivo de produção acima de 500 linhas (mantém FR-8.2).
