# Spec — Transkriptor v1.5

## F10.A — Detecção estrita

- **FR-10.A1** Apenas sinal forte pode iniciar uma reunião. Microfone isolado,
  independentemente da duração, nunca retorna `"iniciou"`.
- **FR-10.A2** Depois do início, a ausência de sinal forte por
  `CONFIRMACAO_FIM_SEM_SINAL_FORTE` ciclos encerra a reunião mesmo que o
  microfone continue ativo.
- **FR-10.A3** Título inequívoco de Meet/Zoom e heartbeat válido da extensão são
  fortes; WhatsApp, players, página inicial do Meet e microfone são fracos ou
  inativos.
- **FR-10.A4** Não existe comando de captura genérica que ignore o detector. A
  ação manual só confirma uma reunião forte já detectada.

## F10.B — Consentimento e UX silenciosa

- **FR-10.B1** Detecção automática solicita consentimento antes de abrir arquivos
  ou dispositivos de captura.
- **FR-10.B2** Apenas `Sim` explícito grava. `Não`, timeout ou erro não gravam e
  suprimem nova pergunta até a reunião terminar.
- **FR-10.B3** Uma reunião gera no máximo uma pergunta.
- **UX-10.B1** Durante a reunião não há toast de trechos, som, piscada ou janela
  por bloco. O estado aparece apenas no ícone/tooltip/menu.
- **UX-10.B2** O backend `plyer` não é usado. Uma notificação eventual reutiliza
  o ícone `pystray` existente e nunca adiciona outro ícone.

## F10.C — Captura desacoplada

- **FR-10.C1** `Transcritor(processar_ao_vivo=False)` não carrega
  `WhisperModel` e grava loopback/microfone continuamente.
- **FR-10.C2** No modo posterior, a fila nunca descarta o bloco mais antigo. A
  escrita em disco acompanha a captura e contabiliza qualquer falha.
- **FR-10.C3** O WAV recebe flush periódico e fecha com header válido.
- **NFR-10.C1** Em gravação, `faster_whisper`, `ctranslate2`, `speechbrain` e
  modelos não são importados pelo processo da bandeja.
- **NFR-10.C2** Gate Windows de 10 min: um processo, um ícone, crescimento de
  memória menor que 100 MB e CPU média menor que 10% de um núcleo, descontado o
  autoteste inicial.

## F10.D — Fila e pós-processamento

- **FR-10.D1** Encerrar a reunião fecha os WAVs, cria job durável e libera a
  captura antes de carregar IA.
- **FR-10.D2** Jobs são arquivos JSON atômicos com estados `pending`,
  `processing`, `ready` ou `failed`; job interrompido volta a `pending` no
  próximo startup.
- **FR-10.D3** Um subprocesso sem janela e de prioridade baixa executa Whisper e
  diarização. A bandeja permanece responsiva e pode capturar nova reunião.
- **FR-10.D4** Falha preserva o áudio e uma mensagem segura, sem conteúdo falado;
  o job pode ser tentado novamente.

## F10.E — Transcrição legível

- **FR-10.E1** Sucesso cria `.txt` UTF-8 atômico na raiz de `transcricoes/`.
- **FR-10.E2** O texto contém início, fim, duração, timestamps e conteúdo; a
  versão diarizada acrescenta rótulos de falante.
- **FR-10.E3** A cópia `.tkpt`, quando habilitada, é adicional. Falha de
  criptografia não apaga nem impede o `.txt` pedido pelo usuário.
- **FR-10.E4** O menu mostra `Em fila`, `Processando`, `Pronta` ou `Falhou` e abre
  a pasta do resultado.

## F10.F — Configuração e chave

- **SEC-10.F1** Escritas parciais usam `config_user.atualizar`; snapshots antigos
  nunca apagam chaves desconhecidas.
- **SEC-10.F2** A chave mestra DPAPI tem armazenamento dedicado atômico, com
  migração do campo legado e sem valor em log.
- **SEC-10.F3** Testes usam `tmp_path`; nenhum teste altera a configuração, chave,
  transcrições ou atalhos reais.
- **SEC-10.F4** Paths de jobs e resultados são resolvidos e validados dentro de
  `PASTA_TRANSCRICOES`; conteúdo de transcrição nunca entra no log ou JSON do job.

## F10.G — Recuperação e retenção

- **FR-10.G1** A ferramenta de recuperação extrai intervalos sem alterar o WAV
  original e valida frames/duração dos destinos.
- **FR-10.G2** As duas reuniões de 2026-08-06 geram `.txt` separados; a segunda
  recebe aviso de lacuna estimada de 285 s.
- **FR-10.G3** Só após os resultados existirem e passarem a auditoria, o arquivo
  combinado, o `.tkpt` ilegível e a captura indevida são movidos para a Lixeira.

## F10.H — Auditoria final

- **NFR-10.H1** Cada T-10 termina com teste direcionado verde e commit próprio.
- **NFR-10.H2** A suíte completa fica 100% verde.
- **NFR-10.H3** Auditoria final cruza cada requisito com código, teste e evidência
  Windows; também revisa qualidade, coerência, privacidade e segurança do diff.
- **NFR-10.H4** Nenhuma conclusão usa apenas documento ou teste estrutural quando
  o requisito exige comportamento real.
