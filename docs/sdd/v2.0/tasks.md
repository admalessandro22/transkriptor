# Tasks — nomes exatos, IA escolhível e instalação em um clique (SDD v2.0)

**Estado em 29/09/2026:** decisões respondidas (`decisoes-usuario.md`); implementação autorizada task a task, a partir de T-15.A1, na ordem DP-15-12. Ordem, trilhas e gates estão em `plan.md`; contratos em `interfaces.md`. Todos os IDs usam o prefixo `T-15`.

Cada task tem os blocos **Arquivos**, **Implementação**, **RED**, **Teste final** e **Aceite**. Os testes citados são entregáveis da própria task. Nenhuma task usa dados reais: fixtures de protocolo são sintéticas, geradas por `tests/js/fixtures/gerar_meet_v2.js`.

Estados possíveis: `PENDING`, `IN_PROGRESS`, `DONE`, `BLOCKED`, `REOPENED` (mesma semântica da v1.8).

## F15.A — relógio e linha do tempo das falas

### T-15.A1 — horário na origem da legenda

- [x] **Requisito:** FR-15.A1. **Depende de:** autorização. **Estado:** `DONE`; evidência: `evidencias/T-15.A1.md`. **Tamanho:** P.
- **Arquivos:**
  - modificar `extension/meet/rtc.js`, `extension/meet/content.js`, `extension/meet/background.js`;
  - criar `tests/js/meet-tempo-origem.test.js`, `tests/test_envelope_v2.py`;
  - modificar `sessao_reuniao.py` (`validar_envelope` aceita v2), `tests/js/content.test.js`.
- **Implementação:**
  - `rtc.js` calcula `agora()` (`timeOrigin + now()`) ao receber cada pacote e publica `t_inicio_ms`/`t_ultimo_ms`, guardando o primeiro por `utterance/dispositivo` num `Map` limitado (LRU de 512);
  - `content.js` preserva `t_inicio_ms` entre revisões (corrige G-01). Emenda de 29/09: `page_perf_ms`/`page_wall_ms` passam para a T-15.A2, única consumidora;
  - `background.js` copia os campos para o envelope v2 sem substituí-los (corrige G-02).
- **RED:**
  - `meet-tempo-origem.test.js::revisao nao altera t_inicio`, `::t_ultimo cresce`, `::flush nao substitui horario`;
  - `test_envelope_v2.py::test_v2_exige_caption_started`, `::test_v1_continua_aceito`, `::test_started_maior_que_last_rejeitado`.
- **Teste final:** `python -m pytest tests/test_envelope_v2.py tests/test_sessao_meet.py tests/test_meet_bridge.py -v`; `npx vitest run tests/js/meet-tempo-origem.test.js tests/js/content.test.js tests/js/meet-rtc.test.js`.
- **Aceite:** com uma fixture de 3 revisões espaçadas em 1,2 s, o envelope final traz `caption_started_ms` igual ao da primeira revisão (±1 ms).

### T-15.A2 — handshake de relógio e conversão para o tempo do áudio

- [x] **Requisito:** FR-15.A2. **Depende de:** A1. **Estado:** `DONE`; evidência: `evidencias/T-15.A2.md` (suíte completa pós-correção pendente por falta de memória). **Tamanho:** M.
- **Arquivos:**
  - criar `relogio_meet.py`, `tests/test_relogio_meet.py`, `tests/js/background-relogio.test.js`;
  - modificar `extension/meet/background.js`, `meet_bridge.py`, `sessao_reuniao.py`, `processador_reuniao.py:169`, `identidade_reuniao.py`, `app_ciclo_reuniao.py` (aviso legado G-14), `config.py`.
- **Implementação:**
  - ping/pong conforme `interfaces.md` §3; `content.js` anexa `page_perf_ms`/`page_wall_ms` a cada lote para o delta página↔service worker;
  - a ponte chama `anotar_handshake` com a melhor amostra;
  - o job leva `offset_ns`, `incerteza_ns` e `first_frame_monotonic_ns`;
  - `identidade_reuniao._tempo_ms` usa `relogio_meet.para_ms_audio`, e o `clock_uncertainty_ms` vem da medida, não da constante 5000;
  - o aviso "Nenhum nome recebido do Meet" passa a consultar o `EventStore` da sessão.
- **RED:**
  - `test_relogio_meet.py::test_menor_rtt_define_offset`, `::test_incerteza_meia_rtt`, `::test_conversao_para_ms_audio`, `::test_sem_amostra_relogio_incerto`;
  - `test_identidade_reuniao.py::test_janela_temporal_aplicada_com_relogio_ok`;
  - `test_nomes_meet_worker.py::test_aviso_sem_nomes_le_event_store`.
- **Teste final:** `python -m pytest tests/test_relogio_meet.py tests/test_identidade_reuniao.py tests/test_nomes_meet_worker.py tests/test_meet_bridge.py tests/test_lock_sem_callback.py tests/test_primeiro_frame.py tests/test_envelope_v2.py tests/test_eventos_meet_store.py -v`; `npx vitest run tests/js/background-relogio.test.js tests/js/background.test.js`; `python scripts/gate_reuniao_real.py --segundos 25` (mexe em captura: `captura_leve.py`).
- **Aceite:** com atraso simulado de 37 ms e jitter de ±10 ms, o offset estimado erra ≤ 15 ms e `relogio_incerto` fica falso.

### T-15.A3 — fila pré-sessão, reconexão e consolidação de revisões

- [ ] **Requisito:** FR-15.A3. **Depende de:** A2. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - modificar `extension/meet/background.js`, `extension/meet/content.js`, `meet_bridge.py:237, 384-396`, `eventos_meet_store.py`, `config.py`;
  - criar `tests/js/background-fila.test.js`, `tests/test_eventos_meet_lote.py`.
- **Implementação:**
  - fila por aba limitada por `FILA_PRE_SESSAO_MAX`/`FILA_PRE_SESSAO_IDADE_MS`, drenada em ordem após `sessao`;
  - consolidação no `content.js` (primeira, ≤ 1/s, final com `caption_final`);
  - `EventStore` lacra por lote (`LOTE_EVENTOS_MS`/`LOTE_EVENTOS_MAX`) e no fim da sessão;
  - excesso de taxa incrementa o contador `descartados_taxa`, que aparece no Diagnóstico.
- **RED:**
  - `background-fila.test.js::eventos antes da sessao sao reenviados em ordem`, `::reconexao nao perde eventos`, `::fila respeita limite`;
  - `test_eventos_meet_lote.py::test_lote_lacra_por_tempo`, `::test_lote_lacra_no_fim`, `::test_idempotente_por_event_id`, `::test_descarte_de_taxa_contado`.
- **Teste final:** `python -m pytest tests/test_eventos_meet_lote.py tests/test_eventos_meet_store.py tests/test_privacidade_eventos.py tests/test_meet_bridge_seguranca.py -v`; `npx vitest run tests/js/background-fila.test.js tests/js/content.test.js`.
- **Aceite:** uma reunião sintética de 30 min com 6 pessoas gera ≤ 60 arquivos de segmento (hoje, ~1 por revisão) e zero perdas na reconexão simulada.

## F15.B — paridade de captura com a Tactiq

### T-15.B1 — idioma da legenda: leitura, Diagnóstico e peso do texto

- [x] **Requisito:** FR-15.B1. **Depende de:** A1. **Estado:** `DONE`; evidência: `evidencias/T-15.B1.md`. **Tamanho:** M (a escrita saiu para a T-15.B1W).
- **Arquivos:**
  - modificar `extension/meet/rtc.js` (`idiomasEm`, `idiomaDoCorpo`, `idioma` na legenda, leitura do `UpdateMediaSession`), `extension/meet/content.js` (capacidade a cada mudança, `caption_lang` na legenda), `extension/meet/background.js` (cópia validada), `sessao_reuniao.py`, `meet_bridge.py` (`idiomas_meet`), `diagnostico.py` e `central_diagnostico.py`, `linha_tempo_falas.py` (`Fala.idioma`), `alinhador_falas.py` e `retranscritor.py` (`idioma_transcricao`);
  - criar `tests/js/meet-idioma.test.js`, `tests/test_idioma_legenda.py`.
- **Implementação:** só leitura; códigos `^[a-z]{2,3}-[A-Z]{2}$`; divergência pela base do idioma (`pt` × `en`); `auto` nunca diverge.
- **RED:** `meet-idioma.test.js` (9 casos, entre eles "a extensão continua só lendo"); `test_idioma_legenda.py` (idioma no envelope, ponte, Diagnóstico, linha do tempo, `test_idioma_divergente_zera_peso_textual`).
- **Teste final:** `python -m pytest tests/test_idioma_legenda.py tests/test_alinhador_falas.py tests/test_diagnostico.py tests/test_meet_bridge.py -v`; `npx vitest run tests/js/meet-idioma.test.js tests/js/meet-rtc.test.js`; `npm run test:e2e -- diagnostico.spec.js csp.spec.js`.
- **Aceite:** legenda em `en-US` numa transcrição `pt` gera o aviso no Diagnóstico e alinhamento sem texto (`estimado=False`, confiança menor), mantendo os nomes pelo tempo; nenhum `send` novo na extensão.

### T-15.B1W — pedir ao Meet a legenda no idioma da transcrição

- [ ] **Requisito:** FR-15.B1W. **Depende de:** B1, DP-15-01 e **captura autorizada de tráfego real** numa reunião de teste. **Estado:** `BLOCKED` (formato do comando desconhecido; ver `evidencias/T-15.B1.md`). **Tamanho:** M.
- **Arquivos:** criar `extension/meet/rtc_idioma.js`, `tests/js/meet-idioma-escrita.test.js`, `tests/js/fixtures/meet-media-session-v1.json` (anonimizada, derivada da captura); modificar `extension/meet/manifest.json`, `extension/meet/content.js`, `central_config.py` (`meet_idioma_legenda`), `config.py`.
- **Implementação:**
  - modo de captura de diagnóstico (desligado por padrão) que registra **localmente**, na reunião de teste, a estrutura (números de campo e tamanhos, sem texto) do pedido de idioma que o próprio Meet envia ao trocar o idioma na interface;
  - a partir dessa estrutura, gerar o pedido com o código desejado e a sequência seguinte;
  - esperar confirmação e registrar o resultado;
  - uma reafirmação quando o canal reabre; nada de retry agressivo.
- **RED:** `meet-idioma-escrita.test.js::pedido reproduz a estrutura observada`, `::nao_alterar nunca envia`, `::timeout vira resultado timeout`, `::um pedido por reabertura`.
- **Teste final:** `npx vitest run tests/js/meet-idioma-escrita.test.js tests/js/meet-idioma.test.js`; `python -m pytest tests/test_idioma_legenda.py -v`.
- **Aceite:** em reunião de teste autorizada, a legenda passa para `pt-BR` sem efeito visível para os outros participantes, e o Diagnóstico mostra o idioma confirmado.

### T-15.B2 — identificação do próprio dispositivo

- [x] **Requisito:** FR-15.B2. **Depende de:** A1. **Estado:** `DONE`; evidência: `evidencias/T-15.B2.md`. **Tamanho:** M.
- **Arquivos:**
  - modificar `extension/meet/rtc.js` (request de `SyncMeetingSpaceCollections`, resposta de `CreateMeetingDevice`), `extension/meet/content.js`, `extension/meet/background.js` (`kind=self_device`), `sessao_reuniao.py`, `linha_tempo_falas.py` (`dispositivo_proprio`), `alinhador_falas.py` e `retranscritor.py` (emenda: a regra mora no alinhador; `identidade_reuniao.py` e `diarizacao_final.py` não mudaram);
  - criar `tests/js/meet-proprio.test.js`, `tests/test_dispositivo_proprio.py`.
- **Implementação:**
  - regex de `spaces/…/devices/…` sobre o corpo, convertida para `dev-<n>`, com o primeiro valor da sessão valendo;
  - o dispositivo próprio recebe o rótulo `<nome> (você)`, e segmentos `audio_source=mic` herdam esse participante;
  - conflito com o perfil de voz vira sugestão, nunca troca silenciosa.
- **RED:**
  - `meet-proprio.test.js::extrai dispositivo do corpo do request`, `::nao aceita segundo valor`;
  - `test_dispositivo_proprio.py::test_mic_herda_participante_proprio`, `::test_proprio_nunca_atribuido_a_outro`, `::test_rotulo_voce_com_nome_meet`.
- **Teste final:** `python -m pytest tests/test_dispositivo_proprio.py tests/test_diarizacao_voce.py tests/test_identidade_reuniao.py -v`; `npx vitest run tests/js/meet-proprio.test.js`.
- **Aceite:** reunião sintética com o usuário e 2 pessoas: 100% das falas do mic rotuladas `Alessandro (você)`.

### T-15.B3 — canal legado, canais do Meet e deduplicação

- [ ] **Requisito:** FR-15.B3. **Depende de:** A1. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - criar `extension/meet/rtc_canais.js`, `tests/js/meet-canais.test.js`, `tests/js/fixtures/meet-captions-legado-v1.bin.json`;
  - modificar `extension/meet/rtc.js`, `extension/meet/manifest.json`, `central_diagnostico.py`.
- **Implementação:**
  - abrir `captions` e `captions_v2` na conexão que recebe `collections`;
  - patch de `createDataChannel` para observar canais do Meet (sem alterar parâmetros);
  - decodificador legado próprio;
  - deduplicação por `dispositivo|versão|texto` em 700 ms, com memória de 30 s e 512 entradas;
  - detecção de `meta#tactiq-rtc`.
- **RED:** `meet-canais.test.js::mesma fala em dois canais vira uma`, `::canal do meet observado`, `::legado decodifica fixture`, `::tactiq detectada`, `::nao altera opcoes do meet`.
- **Teste final:** `python -m pytest tests/test_diagnostico.py -v`; `npx vitest run tests/js/meet-canais.test.js tests/js/meet-rtc.test.js`.
- **Aceite:** fixture com os dois canais ativos produz exatamente N falas (sem duplicatas); o Diagnóstico mostra "Tactiq ativa nesta aba".

### T-15.B4 — saúde do canal e recuperação de silêncio

- [ ] **Requisito:** NFR-15.B4. **Depende de:** B3. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - modificar `extension/meet/rtc_canais.js`, `extension/meet/content.js` (detecção de fala pelo tile), `meet_bridge.py` (`kind=health`), `central_diagnostico.py`, `templates/diagnostico.html`;
  - criar `tests/js/meet-saude.test.js`, `tests/test_saude_legendas.py`.
- **Implementação:**
  - vigia a cada 10 s: `LEGENDA_SILENCIO_MS` sem pacote com fala recente (30 s) dispara a recriação dos canais, até 3 vezes;
  - reabertura em queda (conexão atual, depois nova a cada 5 s, até 5 vezes);
  - contadores e esqueleto sem conteúdo;
  - resumo ao fim da reunião no Diagnóstico com o motivo provável ("canal nunca abriu", "idioma divergente", "parsing falhou após build X").
- **RED:**
  - `meet-saude.test.js::silencio com fala recria canais`, `::silencio sem fala nao recria`, `::maximo 3 tentativas`, `::esqueleto nao contem texto`;
  - `test_saude_legendas.py::test_resumo_sem_pii`, `::test_motivo_canal_nunca_abriu`.
- **Teste final:** `python -m pytest tests/test_saude_legendas.py tests/test_central_diagnostico.py -v`; `npx vitest run tests/js/meet-saude.test.js`.
- **Aceite:** o esqueleto de uma fixture com texto "segredo" não contém a string nem bytes dela; o Diagnóstico renderiza o resumo sob a CSP real.

### T-15.B5 — chat do Meet (opcional)

- [ ] **Requisito:** FR-15.B5. **Depende de:** B3 e DP-15-03. **Estado:** `PENDING`. **Tamanho:** P.
- **Arquivos:**
  - modificar `extension/meet/rtc_canais.js` (`meet_messages`, `CreateMeetingMessage`), `content.js`, `background.js` (`kind=chat`), `central_config.py` (`meet_capturar_chat`), `resultado_reuniao.py` (exportação);
  - criar `tests/js/meet-chat.test.js`, `tests/test_chat_meet.py`.
- **Implementação:** decodificação de chat só com a configuração ligada; autor pelo mapa de dispositivos; linha `[chat]` na exportação.
- **RED:** `meet-chat.test.js::desligado nao decodifica`, `::ligado emite chat com autor`; `test_chat_meet.py::test_exportacao_marca_chat`, `::test_desligado_nao_persiste`.
- **Teste final:** `python -m pytest tests/test_chat_meet.py tests/test_privacidade_eventos.py -v`; `npx vitest run tests/js/meet-chat.test.js`.
- **Aceite:** padrão ligado (DP-15-03); com a opção desligada, o chat fica ausente, provado pelo `EventStore` sem eventos `chat`.

## F15.C — atribuição exata por fala

### T-15.C1 — tempos por palavra no Whisper

- [x] **Requisito:** FR-15.C1. **Depende de:** autorização. **Estado:** `DONE`; evidência: `evidencias/T-15.C1.md`. **Tamanho:** P.
- **Arquivos:** modificar `audio_fontes.py:75`, `resultado_pipeline.py`, `resultado_edicao.py` (classe canônica e payload; emenda: `resultado_storage.py` não precisou mudar), `assistente.py` (leitura sem palavras); criar `tests/test_palavras_whisper.py`.
- **Implementação:** `word_timestamps=True`; persistir `words` compactas; leitura retrocompatível; medir o custo de tempo em CPU (evidência).
- **RED:** `test_palavras_whisper.py::test_segmento_tem_palavras`, `::test_resultado_antigo_sem_palavras_carrega`, `::test_texto_do_segmento_inalterado`.
- **Teste final:** `python -m pytest tests/test_palavras_whisper.py tests/test_resultado_pipeline.py tests/test_processador_reuniao.py -v`; `python scripts/gate_reuniao_real.py --segundos 25`.
- **Aceite:** o gate de 25 s gera `.txt` legível; o aumento de tempo de transcrição fica ≤ 15% (medido e registrado).

### T-15.C2 — alinhamento legenda↔Whisper e corte por troca de falante

- [x] **Requisito:** FR-15.C2. **Depende de:** A2, C1. **Estado:** `DONE`; evidência: `evidencias/T-15.C2.md`. **Tamanho:** G.
- **Arquivos:**
  - criar `linha_tempo_falas.py`, `alinhador_falas.py`, `tests/test_linha_tempo_falas.py`, `tests/test_alinhador_falas.py` (gerador sintético no próprio teste, no lugar de `tests/fixtures/alinhamento/`);
  - modificar `retranscritor.py` (ponto de encaixe real, antes da diarização), `resultado_pipeline.py`, `processador_reuniao.py` (log), `relogio_meet.py` (`ts_fim_sec`), `status_seguro.py`, `config.py`. O `diarizacao_final.py` não precisou mudar.
- **Implementação:** conforme `interfaces.md` §4; atraso global por grade, refino por janela, atribuição por palavra, corte com fragmento mínimo e marcação de `overlap`.
- **RED:**
  - `test_alinhador_falas.py::test_recupera_atraso_simulado` (−1200 ms ± 50);
  - `::test_deriva_linear_refinada`;
  - `::test_segmento_com_duas_vozes_e_cortado`;
  - `::test_frase_curta_atribuida_por_tempo` ("sim" de 0,4 s);
  - `::test_sobreposicao_sem_desempate_marca_overlap`;
  - `::test_concordancia_baixa_reduz_confianca`;
  - `test_linha_tempo_falas.py::test_revisoes_viram_uma_fala`, `::test_sem_relogio_retorna_vazio`.
- **Teste final:** `python -m pytest tests/test_alinhador_falas.py tests/test_linha_tempo_falas.py tests/test_nomes_meet_worker.py tests/test_processador_reuniao.py tests/test_relogio_meet.py -v` (emenda: `test_diarizacao_final.py` não existe no repositório).
- **Aceite:** em fixture sintética de 10 min com 4 falantes, atraso de −900 ms e deriva de 200 ms, ≥ 98% das palavras recebem o dispositivo correto.

### T-15.C3 — política de nomes automática calibrada

- [ ] **Requisito:** FR-15.C3. **Depende de:** C2, B2 e DP-15-02. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:** modificar `identidade_reuniao.py`, `correlacionador.py` (remover `correlacionar_segmento`/`correlacionar_por_legenda` mortos), `resultado_pipeline.py`, `static/js/participantes.js`, `config.py` (`MODO_AUTO_NOMES` → configurável); criar `tests/test_politica_nomes.py`.
- **Implementação:**
  - votação por cluster com peso de duração;
  - aplicação automática acima dos limiares;
  - sugestão caso contrário;
  - correção manual preservada;
  - a Central mostra a origem e a confiança por falante.
- **RED:** `test_politica_nomes.py::test_cluster_dominante_recebe_nome`, `::test_cluster_dividido_fica_sugestao`, `::test_homonimos_nao_fundem`, `::test_manual_prevalece_no_reprocessamento`, `::test_relogio_incerto_nao_aplica_auto`.
- **Teste final:** `python -m pytest tests/test_politica_nomes.py tests/test_identidade_reuniao.py tests/test_correlacionador.py tests/test_renomear_falante_flow.py tests/test_api_participantes_reuniao.py -v`; `npm run test:e2e -- participantes-painel.spec.js participantes-revisao.spec.js`.
- **Aceite:** nenhum `FALANTE_XX` sem sufixo "identificação pendente"; os testes E2E mostram a origem "Meet" e a confiança.

### T-15.C4 — transcrição do Meet como saída e reserva

- [ ] **Requisito:** FR-15.C4. **Depende de:** C2. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:** criar `transcricao_meet.py`, `tests/test_transcricao_meet.py`, `tests/e2e/transcricao-meet.spec.js`; modificar `resultado_reuniao.py`, `central_reunioes.py`, `templates/reunioes.html`, `static/js/reunioes.js`.
- **Implementação:**
  - agrupamento por falante contíguo (intervalo ≤ 5 s e ≤ 6 frases por bloco);
  - artefato cifrado como os demais;
  - aba "Transcrição do Meet" na reunião;
  - preenchimento de lacunas > 2 s na transcrição principal.
- **RED:** `test_transcricao_meet.py::test_agrupa_mesmo_falante`, `::test_quebra_por_intervalo`, `::test_lacuna_preenchida_marcada`, `::test_sem_legendas_sem_artefato`; `transcricao-meet.spec.js::aba mostra horario e nome escapados`.
- **Teste final:** `python -m pytest tests/test_transcricao_meet.py tests/test_resultado_pipeline.py -v`; `npm run test:e2e -- transcricao-meet.spec.js`.
- **Aceite:** nome com `<script>` renderizado como texto; exportação da transcrição do Meet no formato da `interfaces.md` §10.

## F15.D — motores de IA configuráveis

### T-15.D1 — provedores de IA unificados (Ollama)

- [ ] **Requisito:** FR-15.D1. **Depende de:** autorização. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - criar `provedores_ia.py`, `detector_ollama.py`, `tests/test_provedores_ia.py`, `tests/test_detector_ollama.py`;
  - modificar `assistente.py:372-385, 422-429`, `assistente_ollama.py`, `central_resumos.py:31-78`, `resumo_reuniao.py`, `config.py:109`, `instalar_helper.py:36-50`.
- **Implementação:**
  - protocolo e `ProvedorOllama` conforme `interfaces.md` §5 e §6;
  - substituir todas as chamadas diretas;
  - streaming normalizado para `Iterator[str]`;
  - `OLLAMA_URL` vira padrão de `ollama_url`, só loopback.
- **RED:**
  - `test_provedores_ia.py::test_ollama_lista_modelos`, `::test_stream_ndjson_normalizado`, `::test_offline_estado_offline`, `::test_url_nao_loopback_recusada`;
  - `test_detector_ollama.py::test_ordem_de_busca`, `::test_ollama_host_normalizado`, `::test_parado_quando_exe_sem_api`, `::test_registro_install_location`;
  - teste de arquitetura: `::test_nenhum_modulo_chama_api_tags_direto`.
- **Teste final:** `python -m pytest tests/test_provedores_ia.py tests/test_detector_ollama.py tests/test_assistente_api.py tests/test_resumo_reuniao.py tests/test_central_resumos.py -v`; `npm run test:e2e -- chat-cancel.spec.js`.
- **Aceite:** o `grep` por `/api/tags` e `/api/chat` fora de `provedores_ia.py` retorna vazio; a Central com Ollama offline se comporta como hoje.

### T-15.D2 — provedor OpenRouter com chave protegida

- [ ] **Requisito:** SEC-15.D2. **Depende de:** D1 e DP-15-04. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - modificar `provedores_ia.py` (ou criar `provedor_openrouter.py`), `crypto_storage.py` (reuso de `_dpapi_protect`/`_dpapi_unprotect` via função pública), `status_seguro.py` (máscara `sk-or-`), `politica_privacidade.py`, `resultado_reuniao.py` (marca de provedor);
  - criar `tests/test_provedor_openrouter.py`.
- **Implementação:**
  - HTTP com `urllib`, timeout e cancelamento;
  - SSE para stream;
  - preferência de não coleta;
  - erros seguros;
  - consentimento com data;
  - marca `Gerado por OpenRouter · <modelo>` no resumo e na resposta.
- **RED:** `test_provedor_openrouter.py::test_chave_nunca_em_log`, `::test_chave_cifrada_dpapi`, `::test_sem_consentimento_recusa`, `::test_chave_invalida_erro_explicito`, `::test_sem_fallback_silencioso`, `::test_sse_normalizado`, `::test_marca_provedor_no_resumo` (HTTP simulado, sem rede real).
- **Teste final:** `python -m pytest tests/test_provedor_openrouter.py tests/test_status_seguro.py tests/test_assistente_seguranca.py -v`.
- **Aceite:** nenhuma requisição real nos testes; `config_user.json` não contém a chave em claro; o `/api/estado` não muda de forma.

### T-15.D3 — configurações de transcrição e de resumos

- [ ] **Requisito:** UX-15.D3. **Depende de:** D1 (D2 para a opção OpenRouter). **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - criar `central_ia.py` (blueprint `/api/ia/*`), `static/js/ia.js`, `tests/test_central_ia.py`, `tests/e2e/configuracoes-ia.spec.js`;
  - modificar `central_config.py`, `templates/configuracoes.html`, `transcricao_core.py:127-146` (dispositivo e precisão), `resumo_reuniao.py:86-91` (modelo escolhido antes da preferência), `static/js/chat.js:164-176` (padrão salvo), `config.py`.
- **Implementação:**
  - seção "Inteligência artificial" com três cartões (Transcrição, Resumos, Assistente);
  - seletor populado pelo provedor, estado, "Testar";
  - confirmação 409 para OpenRouter com texto de consequência;
  - campo de chave sem eco.
- **RED:**
  - `test_central_ia.py::test_modelos_do_provedor`, `::test_openrouter_exige_confirmacao`, `::test_chave_nao_retorna`, `::test_resumo_usa_modelo_configurado`, `::test_whisper_dispositivo_aplicado`;
  - `configuracoes-ia.spec.js::seletor lista modelos do ollama`, `::ollama offline mostra acao`, `::chave mascarada`, `::teclado e axe sem violacoes`.
- **Teste final:** `python -m pytest tests/test_central_ia.py tests/test_central_config.py tests/test_transcricao_core.py -v`; `npm run test:e2e -- configuracoes-ia.spec.js csp.spec.js`.
- **Aceite:**
  - capturas sintéticas claro/escuro;
  - trocar o modelo de resumo e gerar resumo sintético usa o modelo escolhido;
  - a CSP continua sem violação.

## F15.E — instalação em um clique

### T-15.E1 — ID fixo da extensão e Origin fixado

- [ ] **Requisito:** SEC-15.E1. **Depende de:** DP-15-05. **Estado:** `PENDING`. **Tamanho:** P.
- **Arquivos:** modificar `extension/meet/manifest.json` (`key`), `meet_bridge.py:37-42, 95-110, 352-359`, `config.py` (`EXTENSAO_IDS_PERMITIDOS`), `extension/meet/README.md`; criar `tests/test_origem_extensao.py`.
- **Implementação:**
  - a chave pública vem do item na loja (ou de um par gerado para desenvolvimento, com a privada fora do repositório);
  - allowlist exata;
  - remoção do token legado.
- **RED:** `test_origem_extensao.py::test_id_permitido_aceito`, `::test_outro_id_recusado`, `::test_token_legado_recusado`, `::test_id_derivado_da_key_confere`.
- **Teste final:** `python -m pytest tests/test_origem_extensao.py tests/test_meet_bridge_seguranca.py tests/test_meet_pareamento_persistente.py -v`.
- **Aceite:** o ID calculado da `key` é igual ao registrado em `config.py` (teste deriva o ID pela regra do Chrome).

### T-15.E2 — pareamento automático por Native Messaging

- [ ] **Requisito:** FR-15.E2. **Depende de:** E1. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:**
  - criar `ponte_nativa.py` (host stdio), `instalador/registrar_host.py`, `tests/test_ponte_nativa.py`, `tests/js/background-nativo.test.js`;
  - modificar `extension/meet/background.js`, `extension/meet/manifest.json` (`nativeMessaging`), `assistente.py`/`central_api.py` (`/api/ponte/codigo`), `meet_pareamento.py`.
- **Implementação:**
  - host com um único comando e segredo local com ACL do usuário;
  - registro HKCU para Chrome e Edge;
  - a extensão tenta o nativo antes de abrir `pairing.html`;
  - desinstalação remove as chaves.
- **RED:**
  - `test_ponte_nativa.py::test_comando_unico`, `::test_outro_comando_recusado`, `::test_origem_nao_permitida_recusada`, `::test_app_desligado_erro`, `::test_registro_hkcu_chrome_edge` (registro em chave temporária de teste);
  - `background-nativo.test.js::sem credencial usa nativo`, `::nativo falha abre pareamento manual`.
- **Teste final:** `python -m pytest tests/test_ponte_nativa.py tests/test_meet_pareamento_persistente.py -v`; `npx vitest run tests/js/background-nativo.test.js tests/js/background-pairing.test.js`.
- **Aceite:** num perfil de teste do Chrome, com autorização, a extensão pareia sem digitação em < 5 s após o app iniciar.

### T-15.E3 — detecção do Ollama e assistente de primeiro uso

- [ ] **Requisito:** FR-15.E3. **Depende de:** D1, D3, E2. **Estado:** `PENDING`. **Tamanho:** M.
- **Arquivos:** criar `templates/primeiro_uso.html`, `static/js/primeiro_uso.js`, `tests/test_primeiro_uso.py`, `tests/e2e/primeiro-uso.spec.js`; modificar `central_ia.py`, `central_paginas.py`, `transkriptor.pyw` (abre o assistente se `assistente_inicial_concluido` é falso), `scripts/warmup_modelos.py` (progresso).
- **Implementação:**
  - passos Hardware/Whisper → IA de resumos → Extensão → Inicialização;
  - download de modelo Ollama com progresso e cancelamento;
  - "Iniciar Ollama" e "Instalar" com confirmação;
  - OpenRouter pelo mesmo fluxo de D3;
  - "Pular" sempre disponível.
- **RED:** `test_primeiro_uso.py::test_estado_inclui_deteccao`, `::test_baixar_modelo_progresso`, `::test_concluido_nao_reabre`; `primeiro-uso.spec.js::ollama online popula seletor`, `::ollama ausente oferece acoes`, `::pular conclui`, `::axe sem violacoes`.
- **Teste final:** `python -m pytest tests/test_primeiro_uso.py tests/test_detector_ollama.py -v`; `npm run test:e2e -- primeiro-uso.spec.js`.
- **Aceite:** com o Ollama desta máquina (0.34.4, 3 modelos), o seletor mostra os 3 modelos. Esse teste manual exige autorização; os automáticos usam simulação.

### T-15.E4 — instalador empacotado sem Python

- [ ] **Requisito:** FR-15.E4. **Depende de:** E2, E3 e DP-15-06/07. **Estado:** `PENDING`. **Tamanho:** G.
- **Arquivos:**
  - criar `instalador/transkriptor.iss` (Inno Setup), `instalador/provisionar.py`, `instalador/README.md`, `.github/workflows/instalador.yml`, `tests/test_instalador_provisionar.py`;
  - modificar `scripts/gate_instalacao.py`, `desinstalar.bat` (vira atalho para o desinstalador), `instalar_helper.py` (reuso da detecção).
- **Implementação** (conforme DP-15-06):
  - setup por usuário em `%LOCALAPPDATA%\Programs\Transkriptor`;
  - runtime provisionado com o `uv` embutido a partir de `requirements/requirements-{cpu|cuda}.lock` (hashes), escolha por `nvidia-smi`;
  - host nativo registrado;
  - página "Ollama detectado: versão, N modelos" (chama `detector_ollama` via `provisionar.py --detectar`);
  - atalhos e inicialização opcional;
  - no fim, "Abrir Transkriptor" leva ao assistente;
  - o desinstalador preserva dados por padrão.
- **RED:** `test_instalador_provisionar.py::test_rota_cpu_sem_nvidia`, `::test_rota_cuda_com_nvidia`, `::test_hash_obrigatorio`, `::test_detectar_json`, `::test_desinstalar_preserva_dados`, `::test_desinstalar_remove_registro`.
- **Teste final:** `python -m pytest tests/test_instalador_provisionar.py tests/test_gate_instalacao.py -v`; `python scripts/gate_instalacao.py --setup dist/TranskriptorSetup.exe` (VM ou Windows Sandbox limpo).
- **Aceite:** em Windows Sandbox sem Python: instalar, abrir, concluir o assistente e desinstalar sem erro, com tempo e tamanho registrados.

### T-15.E5 — distribuição da extensão pela loja

- [ ] **Requisito:** FR-15.E5. **Depende de:** E1 e DP-15-05. **Estado:** `PENDING`. **Tamanho:** P (mais o prazo de revisão da loja).
- **Arquivos:** criar `scripts/empacotar_extensao.py`, `extension/meet/LOJA.md` (textos, justificativas de permissão), `docs/PRIVACIDADE-EXTENSAO.md`, `tests/test_empacotar_extensao.py`; modificar `extension/meet/README.md`, `templates/primeiro_uso.html` (links da loja), `config.py` (URLs da loja).
- **Implementação:**
  - zip determinístico sem `key`, sem testes e sem arquivos de desenvolvimento;
  - versão conferida com `config.VERSAO`;
  - textos da loja em PT-BR explicando o uso local;
  - a publicação é feita pelo usuário (DP-15-05).
- **RED:** `test_empacotar_extensao.py::test_zip_sem_key_nem_testes`, `::test_versao_confere`, `::test_permissoes_minimas`, `::test_zip_deterministico`.
- **Teste final:** `python -m pytest tests/test_empacotar_extensao.py -v`.
- **Aceite:** o zip passa na validação local do Chrome (carregar o zip extraído) e o link da loja abre pelo assistente.

## F15.F — medição e fechamento

### T-15.F1 — corpus consentido, métrica de nomes e gate final

- [ ] **Requisito:** NFR-15.F1. **Depende de:** todas as anteriores, autorização para reuniões reais e consentimento dos participantes. **Estado:** `PENDING`. **Tamanho:** G.
- **Arquivos:** criar `scripts/avaliar_nomes.py`, `tests/test_avaliar_nomes.py`, `evidencias/GATE-FINAL.md`; modificar `config.py` (limiares calibrados), `docs/MANUAL-USUARIO.md`, `AGENTS.md` (tabela de versões).
- **Implementação:**
  - métrica por palavra (correta, errada, sem nome) contra o gabarito;
  - gabarito vindo da transcrição nativa do Meet quando a conta permitir, ou de anotação manual;
  - calibração com validação cruzada entre reuniões;
  - gate de 600 s;
  - Chrome e Edge;
  - Tactiq ligada e desligada;
  - instalação limpa.
- **RED:** `test_avaliar_nomes.py::test_metrica_por_palavra`, `::test_errado_distinto_de_sem_nome`, `::test_relatorio_sem_texto`.
- **Teste final:** `python -m pytest tests/ -v`; `python scripts/avaliar_nomes.py --corpus <pasta consentida>`; `python scripts/gate_reuniao_real.py --segundos 600`.
- **Aceite:** metas do `concept.md` atingidas ou exceção registrada e aceita pelo usuário; decisão de versão (DP-15-08) registrada.
