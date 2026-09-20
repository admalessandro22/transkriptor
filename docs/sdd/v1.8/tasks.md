# Tasks — confiabilidade e identificação de participantes

**28 tarefas propostas; 10 DONE (T-13.A1–A2, T-13.B1–B3, T-13.C1–C3, T-13.D1, T-13.D3) e 18 pendentes/bloqueadas.** Ordem, checkpoint e gates: `plan.md`. Contratos: `spec.md`. Prefixo de todos os IDs: `T-13`. Cada item inclui também o ciclo de teste/commit obrigatório de `plan.md`.

Para execução por outra LLM, `interfaces.md` e `executor-llm.md` são leitura obrigatória. Os blocos **Arquivos**, **Implementação**, **RED**, **Teste final** e **Aceite** de cada task são cumulativos, não alternativas. O agente não pode trocar nomes de interfaces, tecnologia decidida, ordem, thresholds ou comportamento de falha sem primeiro emendar os documentos e obter revisão.

As decisões DU-01–DU-16 de `decisoes-usuario.md` estão aprovadas. Não perguntar novamente durante A–G. H1–H3 permanecem bloqueadas por tipo/edição da conta Google e autorização própria.

Os arquivos de teste novos são entregáveis da implementação futura. Nomes de casos abaixo são seletores planejados, não testes que já passaram. Em cada task: escrever o teste → confirmar RED de comportamento → implementar → rodar arquivo completo e regressões → registrar evidência → commit. Não usar erro de import como RED suficiente.

## F13.A — base verificável

### T-13.A1 — reconciliar a fonte SDD

- [x] **Requisito:** NFR-13.A1. **Depende de:** revisão deste plano. **Estado:** `DONE`; evidência: `evidencias/T-13.A1.md`.
- **Arquivos:** modificar `AGENTS.md`, `docs/sdd/v1.6/plan.md`, `docs/sdd/v1.6/concept.md`, `docs/VERIFICACAO.md`, `scripts/verificar_fase.py`; criar `tests/test_sdd_rastreabilidade.py` e índice `docs/sdd/README.md`; preservar e referenciar `docs/sdd/v1.8/decisoes-usuario.md`.
- **Implementação:** distinguir release 1.7 vigente e proposta 1.8; corrigir referência v1.5 no passo de execução; manter evidências antigas como históricas. Registrar todo requisito novo e tarefa/gate correspondente; exigir que o índice ativo aponte para decisões, interfaces e protocolo executor; verificar que arquivos/selectores existem ao executar uma fase, sem inferir sucesso por “≥474”.
- **RED:** `test_referencia_ativa_nao_aponta_tasks_legadas`, `test_requisito_sem_task_reprova` e `test_indice_referencia_decisoes_confirmadas` devem acusar a inconsistência, não importar produto.
- **Teste final:** `python -m pytest tests/test_sdd_rastreabilidade.py tests/test_versao.py -v`.
- **Aceite:** um índice ativo coerente; v1.7 continua sendo versão do executável; nenhum histórico foi reescrito como se tivesse novos testes.

### T-13.A2 — gate de fala e testes JavaScript reais

- [x] **Requisito:** NFR-13.A2. **Depende de:** A1. **Estado:** `DONE`; evidência: `evidencias/T-13.A2.md`.
- **Arquivos:** modificar `scripts/gate_reuniao_real.py`, `tests/conftest.py`; criar `tests/test_gate_reuniao_qualidade.py`, `package.json`, lock de npm, `playwright.config.js`, `tests/js/` e `tests/e2e/`.
- **Implementação:** separar extração de falas reconhecidas do cabeçalho; no gate sintético exigir conteúdo lexical da frase conhecida e rejeitar marcador de ausência. Runner JS carrega os módulos reais, sem espelho Python. Fixtures devem fornecer relógio controlado, WAVs sintéticos por fonte e servidores temporários com encerramento garantido. Playwright testa build/source reais e extensão em perfil isolado.
- **RED:** `test_cabecalho_nao_e_fala`, `test_ausencia_de_fala_reprova`, `test_frase_esperada_precisa_aparecer`; teste JS que execute uma função real e falhe se sua implementação for removida.
- **Teste final:** `python -m pytest tests/test_gate_reuniao_qualidade.py tests/test_log_isolado.py tests/test_isolamento_estado_local.py -v`; `npm run test:unit`.
- **Aceite:** teste com só metadados é vermelho no código antigo; cenário com frase reconhecida passa. Não tocar áudio real para validar esses casos unitários.

## F13.B — integridade antes de novas fontes

### T-13.B1 — exclusão entre processos e lease de job

- [x] **Requisito:** FR-13.B1. **Depende de:** A2. **Estado:** `DONE`; evidência: `evidencias/T-13.B1.md`.
- **Arquivos:** modificar `fila_processamento.py`, `app_processamento.py`, `processador_reuniao.py`; criar `fila_lock.py`, `tests/test_fila_concorrencia.py`.
- **Implementação:** lock de arquivo Windows por job em todas as operações read-modify-write; revisão monotônica e lease com PID, criação do processo e nonce. Claim, heartbeat, registro de PID e conclusão usam o mesmo controle. Recuperar só proprietário inexistente/expirado; PID reutilizado não valida lease. Job corrompido vai para quarentena com erro visível, sem impedir os outros.
- **RED:** `test_registrar_pid_nao_reverte_processing`, `test_dois_workers_um_claim`, `test_startup_nao_reivindica_worker_vivo`, `test_json_corrompido_nao_bloqueia_fila`.
- **Teste final:** `python -m pytest tests/test_fila_concorrencia.py tests/test_fila_processamento.py tests/test_worker_observabilidade.py -v`.
- **Aceite:** ensaio concorrente com barreiras entre leitura e escrita; um proprietário por job, sem perda de PID/estado nem duas transcrições.

### T-13.B2 — retenção vinculada a resultado validado

- [x] **Requisito:** FR-13.B2. **Depende de:** B1. **Estado:** `DONE`; evidência: `evidencias/T-13.B2.md`.
- **Arquivos:** modificar `retencao_audio.py`, `fila_processamento.py`, `processador_reuniao.py`; criar `artefatos.py`, `resultado_reuniao.py` (manifesto inicial), `tests/test_retencao_resultado.py`.
- **Implementação:** `resultado_reuniao.validar_manifesto(path, root) -> bool` verifica versão, artefatos, tamanho/hash e estado; `retencao_audio.pode_expirar(audio, jobs, manifesto, agora) -> bool` exige resultado válido, ausência de trabalho dependente e sete dias completos contados de `manifesto.created_at`. Resultado de STT sem fala é identificado como tal, não como transcrição útil. Transcrição/resultado não têm expiração automática. Oferecer inventário/dry-run; executar exclusão apenas de IDs/caminhos já resolvidos e confirmados.
- **RED:** `test_cabecalho_nao_libera_audio`, `test_job_pending_bloqueia_retencao`, `test_hash_divergente_preserva_original`, `test_antes_de_sete_dias_preserva_audio`, `test_resultado_confirmado_apos_sete_dias_libera_so_alvo`, `test_resultado_nao_expira_automaticamente`.
- **Teste final:** `python -m pytest tests/test_retencao_resultado.py tests/test_retencao_audio.py tests/test_processador_reuniao.py -v`.
- **Aceite:** usar só arquivos temporários; conferir cardinalidade de remoção e hash dos arquivos preservados.

### T-13.B3 — progresso, cancelamento e recuperação do worker

- [x] **Requisito:** FR-13.B3. **Depende de:** B1–B2. **Estado:** `DONE`; evidência: `evidencias/T-13.B3.md`.
- **Arquivos:** modificar `app_processamento.py`, `processador_reuniao.py`, `fila_processamento.py`, `config.py`; criar `tests/test_worker_liveness.py`.
- **Implementação:** progresso por etapa/unidades e heartbeat, deadlines da spec, retry até duas tentativas e cancelamento cooperativo. Encerramento forçado só do PID com lease validado, após timeout documentado. Estado `failed/cancelled` preserva fontes; fila segue para o próximo job; falha de import antes do claim não gera reinício infinito.
- **RED:** `test_worker_vivo_sem_progresso_libera_fila`, `test_cancelar_preserva_audio`, `test_retry_tem_limite`, `test_progresso_real_renova_deadline`.
- **Teste final:** `python -m pytest tests/test_worker_liveness.py tests/test_worker_observabilidade.py tests/test_processador_reuniao.py -v`.
- **Aceite:** subprocesso controlado que trava e subprocesso que progride lentamente recebem tratamentos distintos; nenhum processo fora do harness é tocado.

## F13.C — qualidade do áudio

### T-13.C1 — progresso de captura e COM em todos os caminhos

- [x] **Requisito:** FR-13.C1. **Depende de:** B3. **Estado:** `DONE`; evidência: `evidencias/T-13.C1.md` (gates físicos 25 s e 600 s APROVADOS em 19/09/2026).
- **Arquivos:** modificar `captura_leve.py`, `watchdog.py`, `transcricao_core.py`, `identificador_voz.py`, `diagnostico.py`, `config.py`; criar `tests/test_captura_progresso.py`.
- **Implementação:** contador e último frame por fonte; erros consecutivos e disco disponível; supervisionar mic e loopback sem confundir silêncio com ausência de frames. Reinício de dispositivo delimita lacuna no resultado. Envolver cadastro de voz em `com_inicializada()`. Após timeout de stop, não fechar/mover um WAV ainda escrito por thread viva; reportar falha de finalização.
- **RED:** `test_thread_viva_sem_frames_gera_erro`, `test_silencio_com_frames_nao_falha`, `test_mic_morto_e_supervisionado`, `test_cadastro_mantem_com`, `test_stop_nao_move_wav_com_escritor_vivo`.
- **Teste final:** `python -m pytest tests/test_captura_progresso.py tests/test_diagnostico.py tests/test_com_audio.py tests/test_watchdog.py tests/test_lock_sem_callback.py tests/test_dubles_fieis.py -v`.
- **Aceite adicional:** gate físico 25 s após GREEN; registrar perda/reconexão do dispositivo em ambiente consentido.

### T-13.C2 — transcrever microfone e loopback

- [x] **Requisito:** FR-13.C2. **Depende de:** C1. **Estado:** `DONE`; evidência: `evidencias/T-13.C2.md` (gate de mic humano APROVADO em 19/09/2026).
- **Arquivos:** modificar `retranscritor.py`, `diarizador.py`, `audio_utils.py`, `processador_reuniao.py`; criar `audio_reader.py`, `audio_fontes.py`, `tests/test_audio_duas_fontes.py`.
- **Implementação:** STT por fonte, origem temporal explícita e fusão cronológica de segmentos; não apenas rotular segmentos do loopback. Leitor unificado WAV/WAV cifrado evita `wave.open` sobre ciphertext. Deduplicar somente eco confirmado por alinhamento acústico/textual; fala simultânea independente permanece. Retornar segmentos com `audio_source` e `overlap`.
- **RED:** `test_frase_exclusiva_mic_aparece`, `test_mic_cifrado_aceito`, `test_eco_nao_duplica_frase`, `test_falas_simultaneas_preservadas`, `test_offset_de_inicio_alinha_fontes`.
- **Teste final:** `python -m pytest tests/test_audio_duas_fontes.py tests/test_captura_mic.py tests/test_diarizacao_voce.py tests/test_retranscritor.py -v`.
- **Aceite adicional:** frase humana consentida exclusiva no mic deve aparecer; comparar texto de ambas as fontes, não só energia RMS.

### T-13.C3 — áudio longo e formatos explícitos

- [x] **Requisito:** NFR-13.C3. **Depende de:** C2. **Estado:** `DONE`; evidência: `evidencias/T-13.C3.md` (F13.C encerrada; gate 600 s reaproveitado de C1).
- **Arquivos:** modificar `retranscritor.py`, `audio_reader.py`, `audio_utils.py`, `crypto_storage.py`, `diarizacao_final.py`; criar `tests/test_audio_streaming.py` e ADR `docs/adr/0001-audio-cifrado-em-blocos.md`.
- **Implementação:** ampliar o reader de C2 para iteração por blocos ≤30 s com leitura de RIFF/chunks correta; suportar PCM 16/24/32 explicitamente ou rejeitar formato não implementado. Resampling usa taxa do arquivo. Evitar `readframes(total)` e conversões globais. Para `.enc` legado AES-GCM monolítico, declarar limite de tamanho e rota de migração. C3 **não implementa um container criptográfico novo**: documenta no ADR requisitos, alternativas e riscos; a decisão/implementação fica em E1 após revisão de segurança.
- **RED:** `test_audio_duas_horas_nao_le_completo`, `test_pcm24_nao_vira_uint8`, `test_chunk_riff_extra_preserva_duracao`, `test_cifrado_legado_excede_limite_com_erro_claro`.
- **Teste final:** `python -m pytest tests/test_audio_streaming.py tests/test_audio_utils.py tests/test_retranscritor.py tests/test_crypto_storage.py -v`.
- **Aceite:** registrar pico de RAM e throughput; comparar roundtrip cifrado/legado; gate físico 600 s encerra F13.C.

## F13.D — nomes de ponta a ponta

### T-13.D1 — sessão e relógio verificáveis

- [x] **Requisito:** FR-13.D1. **Depende de:** C3. **Estado:** `DONE`; evidência: `evidencias/T-13.D1.md`.
- **Arquivos:** criar `sessao_reuniao.py`, `tests/test_sessao_meet.py`; modificar `meet_bridge.py`, `app_ciclo_reuniao.py`, `deteccao_reuniao.py`.
- **Implementação:** contratos `SessaoReuniao` e envelope da spec; um estado por conexão/aba/conferência. Selecionar a sessão consentida e não confundir recusa/reconexão. Capturar primeira amostra monotônica e âncora UTC; estimar offset/RTT no handshake; marcar tempo incerto em vez de aplicar nomes pelo relógio errado.
- **RED:** `test_duas_abas_nao_se_encerram`, `test_evento_antigo_nao_entra_sessao`, `test_mudanca_relogio_nao_desloca_audio`, `test_evento_antes_do_consentimento_descartado`.
- **Teste final:** `python -m pytest tests/test_sessao_meet.py tests/test_deteccao_multi_fonte.py tests/test_portao_consentimento.py -v`.
- **Aceite:** sequências fora de ordem/repetidas são rejeitadas/deduplicadas; uma conferência não recebe título ou nome da outra.

### T-13.D2 — transporte autenticado da extensão

- [ ] **Requisito:** SEC-13.D2. **Depende de:** D1.
- **Arquivos:** criar `extension/meet/background.js`, `extension/meet/pairing.html`, `extension/meet/pairing.js`, `tests/e2e/meet-transport.spec.js`; modificar manifest, content script, `meet_bridge.py`, configuração da ponte e testes de segurança existentes.
- **Implementação:** content script→service worker→WS; validar sender URL/origin/tab e top-frame. Pairing local de uso único iniciado no app provisiona credencial do worker; não embutir segredo em `config.js`. Rotação/revogação e expiração por sessão; origin exato de extensão autorizada, rejeitar ausência no listener de produção. Limites da spec no WebSocket (`max_size` no servidor) e no parser; estados tipados, reconnect com backoff/jitter e prontidão confirmada.
- **RED:** testes de prefixo enganoso, token antigo, sender de outro site, ausência de Origin, oversized frame, aba recarregada, worker suspenso e porta ocupada.
- **Teste final:** `python -m pytest tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py -v`; `npm run test:e2e -- meet-transport.spec.js`.
- **Aceite:** demonstrar handshake WebSocket autenticado no Chrome e no Edge para Windows; evidência de um navegador não substitui o outro. Não “corrigir” desativando autenticação. Native Messaging está fora da v1.8 e só pode entrar em spec futura.

### T-13.D3 — roster e parser de legendas confiável

- [x] **Requisito:** FR-13.D3. **Depende de:** D2 (implementação; gate de navegadores pendente). **Estado:** `DONE` (automatizado+fixtures); evidência: `evidencias/T-13.D3.md`.
- **Arquivos:** criar `extension/meet/parser.js`, `tests/js/meet-parser.test.js`, fixtures HTML anonimizadas versionadas; modificar `extension/meet/content.js` e README.
- **Implementação:** exportar funções reais de extração, preferir atributos semânticos, separar roster de speaker activity. Capturar IDs quando disponíveis, marcar IDs locais como efêmeros e não fundir homônimos. Eventos de legenda possuem ID/revisão; observar alterações relevantes com debounce e emitir última revisão sem repetir o mesmo bloco indefinidamente. Opacidade não prova fala. Seletor desconhecido emite capacidade indisponível.
- **RED:** tile visível silencioso, homônimos, fala com câmera desligada, revisão de legenda, duplicação de MutationObserver, DOM sem seletores e legenda desligada.
- **Teste final:** `npm run test:unit -- tests/js/meet-parser.test.js`; `npm run test:e2e -- meet-transport.spec.js`; regressão Python de normalização.
- **Aceite:** fixtures executam o JS entregue; excluir dependência do parser Python espelhado como prova funcional, preservando os testes de protocolo úteis.

### T-13.D4 — persistir eventos privados continuamente

- [ ] **Requisito:** SEC-13.D4. **Depende de:** D1–D3.
- **Arquivos:** criar `eventos_meet_store.py`, `tests/test_eventos_meet_store.py`; modificar `meet_bridge.py`, `app_ciclo_reuniao.py`, `config.py`.
- **Implementação:** `EventStore` usa `ArtifactRef`/`ArtifactCipher` de `artefatos.py`; drenar a fila ao menos a cada segundo; journal cifrado e ACK durável. O adaptador inicial encapsula `crypto_storage.salvar_bytes_arquivo`/`ler_bytes_arquivo`, sem duplicar AES-GCM. Guardar evento por sessão/seq, recuperar último registro íntegro após crash, contar descartes e bloquear nova coleta de conteúdo se cifra indisponível. Consentimento/revogação filtra antes de persistir; heartbeat mínimo continua independente. Evento bruto só fica elegível para exclusão sete dias após `ResultManifest` válido; antes disso e durante reprocessamento é preservado.
- **RED:** `test_mil_eventos_preserva_o_final`, `test_ack_exige_durabilidade`, `test_crash_recupera_prefixo_integro`, `test_sem_chave_nao_grava_legenda`, `test_revogacao_interrompe_conteudo`, `test_eventos_expiram_so_sete_dias_apos_resultado_valido`.
- **Teste final:** `python -m pytest tests/test_eventos_meet_store.py tests/test_meet_bridge_seguranca.py tests/test_log_isolado.py -v`.
- **Aceite:** carga sintética de 2 h e limite de spool; nenhum nome/texto aparece em job/log; excesso aparece no estado de qualidade.

### T-13.D5 — entregar os eventos ao worker

- [ ] **Requisito:** FR-13.D5. **Depende de:** B1, D4.
- **Arquivos:** modificar `app_processamento.py`, `fila_processamento.py`, `processador_reuniao.py`, `retranscritor.py`, `diarizacao_final.py`; criar `tests/test_nomes_meet_worker.py`.
- **Implementação:** selar eventos e passar `ArtifactRef`, relógios e preferências da sessão no job v2. Novo worker carrega/valida/decifra o artefato e fornece eventos à diarização. Jobs v1 sem evento resultam em identificação indisponível; não recuperam nomes fictícios. Snapshot inclui rótulo do usuário e opção de vozes conhecidas, sem depender de alteração de configuração posterior.
- **RED:** `test_nome_atravessa_job_e_worker_novo`, `test_restart_preserva_eventos`, `test_hash_incorreto_recusa_eventos`, `test_job_v1_sem_nome_nao_fabrica_participante`.
- **Teste final:** `python -m pytest tests/test_nomes_meet_worker.py tests/test_processador_reuniao.py tests/test_retranscritor.py tests/test_fila_processamento.py -v`.
- **Aceite:** comparar resultado final de processo novo com eventos sintéticos Ana/Bruno; verificar nome no segmento, não apenas argumento passado ao mock.

### T-13.D6 — atribuição conservadora e calibrada

- [ ] **Requisito:** FR-13.D6. **Depende de:** D5.
- **Arquivos:** criar `identidade_reuniao.py`, `tests/test_identidade_reuniao.py`; modificar `correlacionador.py`, `diarizador.py`, `config.py`.
- **Implementação:** retornar `Atribuicao`, não string arbitrária. Considerar janela/offset, texto, duração de atividade, origem e conflitos; restringir fallback de atividade a evento do tipo correto. Legenda lexicalmente incompatível não vira prova temporal. Confirmado manual prevalece; conflito com mic/voz produz pendência. Calibrar limiares em conjunto separado e gravar versão de calibração. Só emitir nome automático com precisão seletiva ≥98% e cobertura elegível ≥80%; abaixo disso retornar `suggested`/`unknown`, exibido como `Identificação pendente`.
- **RED:** `test_legenda_sem_match_nao_substitui_voce`, `test_empate_produz_unknown`, `test_homonimos_exigem_id`, `test_sobreposicao_nao_forca_um_nome`, `test_evidencia_suficiente_nomeia`.
- **Teste final:** `python -m pytest tests/test_identidade_reuniao.py tests/test_correlacionador.py tests/test_diarizacao_voce.py -v`.
- **Aceite:** publicar precisão, cobertura e abstinência; meta da spec só libera modo automático se sustentada pelo corpus. Até lá exibir sugestão revisável.

### T-13.D7 — resultado nomeado e correção por reunião

- [ ] **Requisito:** FR-13.D7. **Depende de:** D6, B2.
- **Arquivos:** ampliar `resultado_reuniao.py`; modificar `renomear_falante_flow.py`, `transkriptor_menu_flows.py`, `assistente.py`, `templates/assistente.html`, `static/assistente.js`; criar `tests/test_resultado_reuniao.py`, `tests/e2e/participants.spec.js`.
- **Implementação:** manifesto/segmentos/participantes persistidos; JSON estruturado é canônico e TXT derivado usa exatamente `[HH:MM:SS] Nome: texto`, uma linha por segmento. Sem atribuição qualificada, usar literalmente `Identificação pendente`. UI escolhe reunião, mostra nome/origem/incerteza e permite editar mapeamento com revisão/hash esperado, undo e reexportação. Centroides não dependem de `app.transcritor` vivo; biometria persistente só em ação separada. Falha parcial de diarização preserva STT e é visível, nunca resultado globalmente completo.
- **RED:** correção após restart, duas reuniões com FALANTE_00, edição concorrente, desfazer, falha de diarização, formato exato do TXT e exportação com `Identificação pendente` sem nome inventado.
- **Teste final:** `python -m pytest tests/test_resultado_reuniao.py tests/test_renomear_falante_flow.py -v`; `npm run test:e2e -- participants.spec.js`.
- **Aceite:** texto/falante/horário iguais no resultado e TXT; concluir gate completo F13.D.

## F13.E — proteção e privacidade

### T-13.E1 — política única de proteção e falha explícita

- [ ] **Requisito:** SEC-13.E1. **Depende de:** D7.
- **Arquivos:** criar `politica_privacidade.py`, `crypto_stream.py`, `tests/test_politica_privacidade.py`, `tests/test_crypto_stream.py`; modificar `requirements.txt`, `crypto_storage.py`, `identificador_voz.py`, `perfil_voz_flow.py`, `audio_reader.py`, `retranscritor.py`, `app_bandeja_menu.py`.
- **Implementação:** modo compatível/protegido e estado efetivo por artefato. Configuração existente sem campo de política migra semanticamente para `compatible`; ausência de configuração (instalação nova) inicia `protected`. `ProtectionUnavailable` impede cadastro novo em claro quando se exige cifra. Falha no áudio preserva material já gravado em área restrita e mostra pendência de proteção. Adicionar provisoriamente `PyNaCl>=1.6.2,<2` ao requisito da v1.8; G1 fixa versão/hash após a matriz. Implementar o formato TKAS/1 definido em `interfaces.md` com bindings SecretStream XChaCha20-Poly1305 do PyNaCl; não reimplementar a primitiva. Se PyNaCl/libsodium não carregar na matriz Windows, o modo protegido de áudio longo fica bloqueado com erro explícito — não criar cifra alternativa. Não gerar nova chave sobre blob existente ilegível. Migração sempre começa em dry-run; remoção real exige lista exata confirmada. Cópias divergentes são preservadas.
- **RED:** instalação nova protegida, instalação existente sem campo compatível, DPAPI indisponível, gravação de cifra falhando, preferências trocadas durante captura, `.enc` antigo e plaintext novo, chave corrompida; TKAS truncado, chunk alterado/reordenado/duplicado e ausência de tag final; dry-run não remove alvo.
- **Teste final:** `python -m pytest tests/test_politica_privacidade.py tests/test_crypto_stream.py tests/test_crypto_storage.py tests/test_identificador_voz.py tests/test_transcricao_crypto.py -v`.
- **Aceite:** zero fallback silencioso; modo compatível ainda entrega TXT como contratado; nenhuma migração de dados reais nesta task sem inventário/fluxo de usuário.

### T-13.E2 — recuperação de todos os artefatos de sessão

- [ ] **Requisito:** SEC-13.E2. **Depende de:** E1, B1.
- **Arquivos:** criar `recuperacao_sessao.py`, `tests/test_recuperacao_sessao.py`; modificar `transcricao_core.py`, `retranscritor.py`, `crypto_storage.py`, bootstrap e retenção.
- **Implementação:** diretório privado por sessão com registro de arquivos ativos e lease. Recuperar raiz legada, `audio/` e `diarizacao_*` conhecidos; resolver contenção/junction antes de qualquer ação. Encerramento abrupto preserva áudio em área restrita, cifra/recupera quando possível e publica resultado do inventário. Nunca varrer TEMP inteiro nem remover arquivo sem provar posse e ausência de escritor.
- **RED:** crash antes do move, durante diarização, após cifra antes do unlink; sessão viva; junction externo; arquivo desconhecido com nome semelhante.
- **Teste final:** `python -m pytest tests/test_recuperacao_sessao.py tests/test_recuperacao_audio.py tests/test_crypto_storage.py -v`.
- **Aceite:** subprocessos de teste são terminados em pontos controlados; toda fonte é recuperada ou explicitamente sinalizada, e hash do original permanece.

### T-13.E3 — contratos e limites da API local

- [ ] **Requisito:** SEC-13.E3. **Depende de:** E2.
- **Arquivos:** modificar `assistente.py`, `assistente_ollama.py`, `config.py`, testes de API/segurança; criar `assistente_validacao.py` e teste E2E de cancelamento.
- **Implementação:** validar JSON objeto, strings e histórico de objetos com role permitido; limite de corpo efetivo no framework, pergunta/histórico/orçamento, limite de requisições simultâneas. Validar Host/Origin com exceções explícitas de cliente local autenticado; proteger bootstrap contra reuso indevido. `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, CSP compatível e anti-framing. Propagar cancelamento ao stream upstream e tarefas de resumo.
- **RED:** arrays/escalar/null, item não objeto, sem Content-Length com corpo grande, token inválido, origem indevida, path traversal, concorrência e desconexão no meio de geração.
- **Teste final:** `python -m pytest tests/test_assistente_seguranca.py tests/test_token_sessao.py tests/test_assistente_api.py -v`; `npm run test:e2e`.
- **Aceite:** erros previstos são 4xx/429, nunca 500; token/realpath atuais permanecem eficazes; sem sockets de geração esquecidos após cancelamento.

### T-13.E4 — eventos de log e ciclo de biometria

- [ ] **Requisito:** SEC-13.E4. **Depende de:** E3.
- **Arquivos:** modificar `status_seguro.py`, `transkriptor.pyw`, `perfil_voz_flow.py`, `renomear_falante_flow.py`, `diagnostico.py`, manual; criar `tests/test_privacidade_eventos.py`.
- **Implementação:** log recebe código de evento e campos operacionais permitidos; texto de fala não compartilha API de status. Exportação de diagnóstico remove nomes, títulos, tokens, paths pessoais e conteúdo. Perfil de voz começa desligado; cadastro persistente exige finalidade/consentimento próprios e ação de exclusão verificável; correção de nome na sessão permanece independente. Perfil permanece até revogação, eventos obedecem sete dias após resultado válido e resultados só saem por exclusão manual. Registrar política aplicada sem dados de fala.
- **RED:** fala começando por “Erro”/“Reunião” ou contendo `.txt`; exceção com token; voz desligada por padrão; correção nominal sem cadastro; revogação remove apenas perfil selecionado e confirma ausência.
- **Teste final:** `python -m pytest tests/test_privacidade_eventos.py tests/test_status_seguro.py tests/test_log_isolado.py tests/test_config_user_voz.py -v`.
- **Aceite:** conteúdo sintético-canário não aparece em logs/diagnósticos/jobs; política de uso deve identificar responsável e base legal sem alegar conformidade só por um checkbox.

## F13.F — assistente utilizável

### T-13.F1 — histórico isolado por reunião e limitado

- [ ] **Requisito:** UX-13.F1. **Depende de:** E4.
- **Arquivos:** modificar `static/assistente.js`, `assistente.py`; criar `tests/e2e/chat-context.spec.js` e testes Python de contrato.
- **Implementação:** associar conversa ao meeting_id e revisão; trocar seleção cancela geração anterior e restaura/limpa histórico do destino. Limitar janela antes de enviar, respeitando orçamento de tokens. Não apagar pergunta digitada antes da validação de envio. Limpar durante stream invalida a resposta tardia por generation_id.
- **RED:** 12ª pergunta recebe resposta; A→B não inclui histórico de A; stream A concluído após seleção B não aparece em B; limpar durante geração não reintroduz mensagens.
- **Teste final:** `npm run test:e2e -- chat-context.spec.js`; `python -m pytest tests/test_assistente_api.py -v`.
- **Aceite:** verificar payloads interceptados e DOM, sem confiar apenas em texto presente no JS.

### T-13.F2 — orçamento e fundamentação de respostas longas

- [ ] **Requisito:** FR-13.F2. **Depende de:** F1.
- **Arquivos:** modificar `assistente_ollama.py`, `resumo_longo.py`; criar `tests/test_resumo_orcamento.py`.
- **Implementação:** reservar tokens de sistema/pergunta/histórico/saída; fallback conservador quando contexto do modelo é desconhecido. Map/reduce recursivo com teto de rodadas/chamadas e verificação de tamanho do consolidado. Preserve IDs/tempos das evidências; erro de Ollama é estado, não resumo a ser resumido. Transcrição é dado delimitado em mensagem separada; instruções nela não acionam ferramentas nem mudam escopo.
- **RED:** resumos intermediários maiores que contexto, pergunta longa, modelo sem metadata, falha no bloco 2, cancelamento e pedido sem evidência; fala tentando instruir o assistente é tratada como conteúdo.
- **Teste final:** `python -m pytest tests/test_resumo_orcamento.py tests/test_assistente_ollama.py -v`.
- **Aceite:** nenhuma chamada excede orçamento no fake que conta tokens; avaliação com modelo local relata fidelidade/citações e limites. Prompt de sistema não é tratado como garantia absoluta contra manipulação.

### T-13.F3 — índice e acessibilidade comportamental

- [ ] **Requisito:** UX-13.F3. **Depende de:** F2.
- **Arquivos:** criar `indice_transcricoes.py`, `tests/test_indice_transcricoes.py`, `tests/e2e/accessibility.spec.js`; modificar API, HTML/CSS/JS.
- **Implementação:** índice de metadados sem preview de fala por padrão, paginação e invalidação por versão de manifesto; não decifrar todos os arquivos para listar. Drawer com foco inicial/restaurado, navegação por teclado, estados de carregamento/erro, versão da reunião explícita e clipboard com erro visível. Substituir testes frágeis de string por interação real, mantendo verificações estáticas úteis.
- **RED:** 1.000 reuniões sem leitura de texto integral, índice desatualizado após job, teclado preso/fora do drawer, seleção perdida ao filtrar, clipboard negado.
- **Teste final:** `python -m pytest tests/test_indice_transcricoes.py tests/test_assistente_api.py -v`; `npm run test:e2e -- accessibility.spec.js`.
- **Aceite:** p95 de consulta registrado; 375/860/1366 sem overflow; teclado/Narrador e contraste verificados, screenshots sem dados reais.

## F13.G — instalação e release

### T-13.G1 — dependências reproduzíveis e CI

- [ ] **Requisito:** NFR-13.G1. **Depende de:** F3.
- **Arquivos:** modificar requisitos/pyproject; criar constraints/locks CPU e CUDA, `.github/workflows/tests.yml`, `docs/DEPENDENCIAS.md`; atualizar instalador para consumir a seleção validada.
- **Implementação:** ambiente virtual limpo com matrizes CPU e CUDA suportadas; fixar API websockets compatível, casal torch/torchaudio e wheel PyNaCl/libsodium para Python 3.12/Windows. Executar auditoria de dependências transitivas e gerar SBOM sem credenciais. CI Windows roda pytest, JS, contratos e artefatos de falha nas rotas possíveis; gate físico é separado e não é falsamente simulado pelo CI. Não corrigir pacotes globais não pertencentes ao produto.
- **RED:** instalar conjunto não compatível deve falhar na pré-checagem com mensagem clara; resolver locks reproduz exatamente a árvore aprovada.
- **Teste final:** em ambiente limpo, `python -m pip check`; `python -m pytest tests/ -q`; `npm ci`; `npm run test:unit`; `npm run test:e2e`.
- **Aceite:** registrar versões, hashes/locks, relatório de CVEs com decisões e licença dos modelos; provar instalação e suíte na rota CPU e na rota CUDA compatível; pacote vulnerável só é aceitável com justificativa específica e prazo.

### T-13.G2 — entrada, instalação e versão coerentes

- [ ] **Requisito:** NFR-13.G2. **Depende de:** G1.
- **Arquivos:** modificar `instalar.bat`, `iniciar.bat`, `iniciar_bandeja.bat`, `desinstalar.bat`, `scripts/resolver_pythonw.py`, `scripts/instalar_helper.py`, `assistente.py`, `transcrever_meet.py`; criar `tests/test_instalacao_caminhos.py`.
- **Implementação:** argumentos corretamente citados, cwd explícito e uso do mesmo venv em todos os caminhos; CLI aceita auto de forma coerente; standalone faz bootstrap de autenticação antes de abrir navegador. Desinstalador detecta processo/gravação e apresenta alvos exatos, preservando dados por padrão. Versão de manifesto/extensão pode ser independente, mas sua relação com release é documentada e gerada.
- **RED:** diretório com espaço/acentos, ausência de Python, venv incompleto, porta ocupada, atalho existente e desinstalação cancelada.
- **Teste final:** `python -m pytest tests/test_instalacao_caminhos.py tests/test_instalador_helper.py tests/test_atalho_desktop.py tests/test_assistente_startup.py tests/test_versao.py -v`.
- **Aceite:** instalação limpa numa pasta de teste, duas inicializações geram uma instância, dados sintéticos preservados ao desinstalar; nenhum atalho real é alterado no teste.

### T-13.G3 — corpus, avaliação física e fechamento

- [ ] **Requisito:** NFR-13.G3. **Depende de:** todas A–G2.
- **Arquivos:** criar `scripts/avaliar_qualidade_reuniao.py`, `tests/test_metricas_qualidade.py`, protocolo `docs/QUALIDADE-REUNIOES.md`; atualizar manual, releases, evidências e versão só depois dos gates.
- **Implementação:** calcular WER/DER, precisão nominal, cobertura total/elegível, abstinências, erros de eco e IC 95%; versionar referência por hashes sem commitar gravações pessoais. Separar conjunto de calibração e teste. Verificar todos os passos físicos de `plan.md`, recursos e recuperação. Conferir correspondência requisito→teste→resultado→commit.
- **RED:** calculador de métricas deve penalizar nome incorreto, reconhecer abstinência e não confundir roster com fala; fixture com erro conhecido produz o valor esperado.
- **Teste final:** `python -m pytest tests/ -q --tb=short`; `python scripts/verificar_fase.py --fase all`; `npm run test:unit`; `npm run test:e2e`; gates físicos 25 s e 600 s; avaliador de corpus; `git diff --check`.
- **Aceite:** metas sustentadas, Chrome e Edge validados, rotas CPU/CUDA documentadas e limitações públicas; caso contrário manter modo sugerido/feature flag e fase aberta. Cada gate real requer autorização específica e sem ela permanece pendente. Bump e release apenas após evidência; push/publicação depende de autorização própria.

## F13.H — complemento Google opcional

### T-13.H1 — OAuth e capacidade da conta

- [ ] **Requisito:** FR-13.H1. **Depende de:** G3, informação de tipo/edição da conta e autorização específica para OAuth. **Estado inicial:** `BLOCKED_EXTERNAL_INFO`; não bloqueia A–G.
- **Arquivos:** criar `google_meet_auth.py`, `google_meet_capabilities.py`, `tests/test_google_capabilities.py`; atualizar configuração/UI de integrações.
- **Implementação:** fluxo OAuth de desktop com state/PKCE e callback loopback; escopo mínimo `meetings.space.readonly`, refresh token protegido por DPAPI, logout/revogação. Capacidade é aferida pela resposta de recursos autorizados e funcionalidade disponível, sem pressupor que toda conta institucional tenha transcrição. Não usar conta de serviço/delegação de domínio por padrão.
- **RED:** state incorreto, token expirado/revogado, 403, conta sem artefato, usuário cancela OAuth e callback repetido.
- **Teste final:** `python -m pytest tests/test_google_capabilities.py -v`; integração real com conta de teste autorizada e sem exportar token.
- **Aceite:** falha mantém funcionamento local; tela distingue participantes disponíveis, transcrição nativa indisponível e falta de permissão.

### T-13.H2 — participantes e entries oficiais

- [ ] **Requisito:** FR-13.H2. **Depende de:** H1.
- **Arquivos:** criar `google_meet_import.py`, `tests/test_google_meet_import.py`; integrar `resultado_reuniao.py` e `identidade_reuniao.py`.
- **Implementação:** resolver conference record específico, paginar roster/sessões/transcrições/entries, correlacionar por participant resource e tempo. Idempotência por resource ID; expiração de 30 dias, múltiplas transcrições, reentrada, homônimos e anônimos. Backoff limitado em 429/5xx; cache por reunião, sem buscar dados de outras reuniões. Importar como fonte distinta; uso no alinhamento local preserva evidência e conflito.
- **RED:** várias páginas, dois homônimos, usuário em dois dispositivos, entry expirada, record incorreto, importação repetida e participantes sem entries.
- **Teste final:** `python -m pytest tests/test_google_meet_import.py tests/test_identidade_reuniao.py tests/test_resultado_reuniao.py -v`.
- **Aceite:** roster sozinho não nomeia segmentos; texto oficial e Whisper continuam distinguíveis; acesso negado não vira lista vazia apresentada como completa.

### T-13.H3 — decisão experimental de Meet Media API

- [ ] **Requisito:** NFR-13.H3. **Depende de:** H1 e elegibilidade Google; não bloqueia núcleo.
- **Arquivos:** criar `docs/experimentos/meet-media-api.md`, `tests/test_meet_media_decision.py`; somente se elegível, protótipo isolado em `experimentos/meet_media/` com testes próprios.
- **Implementação:** conferir documentação e participação no programa para projeto/principal/todos os participantes; registrar escopos, codecs, consentimento, restrições de idade/plataforma e custos operacionais. Piloto resolve CSRC/participante dinamicamente, troca de stream, desconexão e revogação. Sem capturar se não houver autorização elegível.
- **RED:** `test_decisao_media_api_exige_elegibilidade_fontes_riscos_e_go_no_go`, `test_go_exige_evidencia_de_csrc_consentimento_e_interrupcao`, `test_no_go_nao_adiciona_dependencia_ao_startup`.
- **Teste final:** checklist de elegibilidade documentado; se elegível, teste integrado com troca de CSRC/stream e participante interrompendo a API. Se não elegível, a entrega é decisão fundamentada de não implantar, sem declarar protótipo validado.
- **Aceite:** decisão go/no-go com evidência, riscos e orçamento; nenhuma dependência experimental adicionada à inicialização normal do app.

## Exemplos concretos de regressões prioritárias

Estes exemplos pertencem aos testes futuros das tasks indicadas e exercitam funções reais. Devem falhar no comportamento antigo e passar após a alteração; imports/interfaces são ajustados no próprio ciclo TDD.

```python
# D6: tests/test_identidade_reuniao.py — regressao do fallback atual
from correlacionador import aplicar_nomes_meet

def test_legenda_sem_match_nao_substitui_voce():
    segmentos = [("VOCÊ", 0.0, 1.0, "alpha beta")]
    eventos = [{"nome": "Pessoa remota", "tipo": "legenda",
                "ts_sec": 0.5, "texto": "gamma delta"}]
    assert aplicar_nomes_meet(segmentos, eventos)[0][0] == "VOCÊ"
```

```python
# D2: tests/test_meet_bridge_seguranca.py
from meet_bridge import origem_permitida

def test_prefixo_localhost_nao_autoriza_dominio_externo():
    assert origem_permitida("http://localhost.example.test") is False

def test_listener_producao_rejeita_origin_ausente():
    assert origem_permitida(None) is False
```

```python
# E1: tests/test_politica_privacidade.py
import numpy as np
import pytest
import crypto_storage
from identificador_voz import salvar_perfil
from politica_privacidade import ProtectionUnavailable

def test_sem_chave_nao_salva_biometria_em_claro(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto_storage, "criptografia_ativa", lambda: True)
    monkeypatch.setattr(crypto_storage, "chave_disponivel", lambda: False)
    alvo = tmp_path / "perfil.npz"
    with pytest.raises(ProtectionUnavailable):
        salvar_perfil(np.ones(192, dtype=np.float32), alvo)
    assert not alvo.exists()
```

`ProtectionUnavailable` tem a assinatura congelada em `interfaces.md` e é criada em E1. O teste só conta como RED comportamental depois que o esqueleto dessa interface importar; um `ImportError` isolado não comprova o defeito. Casos adicionais/negativos de cada task são obrigatórios além destes exemplos.

## Registro de conclusão por tarefa

Criar `evidencias/T-13.Xn.md` com: requisito; commit-base; arquivos; RED observado; GREEN observado; regressão/gate; ambiente; limitações; SHA do commit final. Marcar a checkbox somente se teste/artefato e evidência existem. H1–H3 continuam opcionais; falta de conta/elegibilidade deve ficar explícita, sem checklist verde fictício.
