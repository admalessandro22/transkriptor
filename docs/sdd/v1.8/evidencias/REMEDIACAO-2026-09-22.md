# Remediação da auditoria v1.8 — índice de execução

- Base auditada: `64b415bdc1ae26100b533cbd3c94abafa2dcb0e8`
- Branch local: `remediacao-auditoria-v18`
- Fonte: `docs/superpowers/plans/2026-09-22-remediacao-auditoria-v18.md`
- Estado global: EM EXECUÇÃO; o produto ainda não atende à definição de pronto.

| Task | Estado | Commit de implementação | Evidência | Gate externo |
|---|---|---|---|---|
| 1 — reconciliação SDD | DONE | `c456714e8124e3d8caf95ab511068ed0d7528ed6` | Este índice; RED exit 1, GREEN 10 passed | Não aplicável |
| 2 — cliente Meet | DONE (automação) | `95045e456100ffa9cf1a5d816ce43b6d86eb4a87` | RED/GREEN abaixo | Demo Chrome/Edge real na Task 12: PENDENTE |
| 3 — bridge/sessão/store | DONE (automação) | `362c63d2fc2b4c3ab4b7dd92e19833d907a843a7` | RED/GREEN e 714 testes abaixo | Navegador real na Task 12: PENDENTE |
| 4 — refs Meet no job | DONE (automação) | `d9e2e7f3a2d4b858077be877a247136d0eedf1c9` | RED/GREEN abaixo | Não aplicável |
| 5 — resultado estruturado | DONE (automação) | `3f505e736a98df4f268ec461d30044876186261b` | RED/GREEN e 720 testes abaixo | Não aplicável |
| 6 — sugestão e revisão UI | DONE (automação) | `ab330cf1a3ffa2bd48d909b72cbbb2cc0559af5c` | RED/GREEN abaixo | Não aplicável |
| 7 — TKAS/1 incremental | DONE (automação) | `f6f11b9af2939c0bed660654482588057decff6f` | RED/GREEN e 726 testes abaixo | Não aplicável |
| 8 — modo protegido em produção | DONE (automação) | `863261d09e2a65b04ba353a7e21245a61133765c`; complemento `8527b1ddaf5bda27b97d7857f3478ba1ef8b7111` | RED/GREEN e 804 testes abaixo | Áudio real na Task 12: PENDENTE |
| 9 — privacidade e mutações HTTP | DONE (automação) | `9737075d30045a3ae5671f0ec57cbccd167edae6` | RED/GREEN e suíte global abaixo | Worker real em processamento: PENDENTE |
| 10 — dependências e CI | DONE (gate local CPU) | `d14ff2a293f100f408955c861f50de8b7f69d104` | Locks, SBOM, 778 testes e auditoria abaixo | CI remoto, CUDA e aceite das exceções: PENDENTES |
| 11 — instalação isolada | DONE (automação) | `e8a6f2fd318bdeaa25ee1658b6a717c419c176cf` | 45 testes; gate CPU isolado abaixo | Duas partidas da bandeja real: PENDENTE |
| 12 — gates e release | IN_PROGRESS (automação concluída) | — | Suíte 804, verificador 238, JS 22, E2E 21 | CI, áudio real, Chrome/Edge, três pessoas, CUDA, bandeja real e autorização de release pendentes |

As evidências históricas `T-13.*.md` permanecem intactas; seus antigos estados DONE não comprovam os contratos reabertos pela auditoria. Cada linha deste índice deve ser detalhada após a respectiva task, com comandos, exit codes, ambiente e SHA real. Gate não executado permanece PENDENTE.

## Task 2 — cliente da extensão Meet

- Estado: DONE para implementação automatizável; demo Chrome/Edge real continua PENDENTE na Task 12.
- Base: `b401848a2e353fea7609dcbb24db72fa68fb1035`
- Resultado: `95045e456100ffa9cf1a5d816ce43b6d86eb4a87`
- Requisito: SEC-13.D2, FR-13.D1 (porção cliente do envelope).
- Ambiente: Windows, Node/Vitest, Playwright Chromium em página sintética; nenhum perfil ou reunião pessoal.
- Arquivos: `extension/meet/background.js`, `content.js`, `parser.js`, `tests/js/background.test.js`, `background-pairing.test.js`, `tests/e2e/meet-transport.spec.js`.
- Baseline: `npm run test:unit -- tests/js/background.test.js` exit 0, 4 testes.
- RED: `npm run test:unit -- tests/js/background-pairing.test.js` exit 1, 6 falhas pelo listener não exportado; `npm run test:unit -- tests/js/background.test.js` exit 1, 3 falhas por ausência de hello/sessão/envelope; `npm run test:e2e -- meet-transport.spec.js` exit 1 para metadados do parser; teste de troca de reunião na mesma aba exit 1 por vazamento de sessão.
- GREEN/regressão em 22/09/2026: `npm run test:unit` exit 0, 21 testes; `npm run test:e2e -- meet-transport.spec.js` exit 0, 6 testes; `git diff --check` exit 0.
- Segurança/dados: somente identificadores e nomes sintéticos em fixtures; token não entra no envelope, e o relógio de recebimento fica para o bridge. Nenhum processo, perfil, áudio ou dado real foi alterado.
- Limitação: o bridge ainda não aceita `hello`/envelope v1. Essa integração pertence à Task 3; a prova de navegador real pertence à Task 12.

## Task 3 — bridge, sessão e EventStore

- Base: `1df93087fd4f1fed6a20975f5633e185133ba08d`.
- Baseline: `python -m pytest tests/test_sessao_meet.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_eventos_meet_store.py -q --tb=short` exit 0, 38 testes.
- RED observado: `test_duas_abas_no_mesmo_socket_mantem_estado_independente` exit 1 por ausência de `vincular`; `test_seal_impede_append_posterior` exit 1 por append aceito após seal; `test_envelope_v1_sem_sessao_nao_cai_na_fila_legada` exit 1 por fallback à fila legada.
- Emenda do contrato: a ordem de continuar autorizou o vínculo em memória do código observado no `hello` à chave opaca, somente com uma sala ativa única. `plan.md`, `spec.md`, `tasks.md`, `interfaces.md` e `executor-llm.md` registram a regra; sem código ou com ambiguidade, o bridge não entrega nomes.
- RED adicional: conexão lógica sem vínculo, fallback v1 para fila legada, `append` após `seal`, falta de `schema_version`, hello sem estado ativo e falta de vínculo no início real do mixin. A suíte completa inicialmente falhou no limite de 500 linhas (`meet_bridge.py`: 543); o pareamento foi extraído para `meet_pareamento.py` e os testes de limite passaram.
- GREEN em 22/09/2026, Windows/Python 3.12/Node: `python -m pytest tests/test_sessao_meet.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_eventos_meet_store.py -v` exit 0, 46 passed; `npm run test:unit` exit 0, 22 passed; `python -m pytest tests/ -q --tb=short` exit 0, 714 passed; `git diff --check` exit 0.
- O teste WebSocket usa duas conexões lógicas no mesmo socket e reabre o segmento cifrado para provar persistência antes do ACK. O relógio de recebimento vem do servidor; nome/texto não entram em log. Não foram usados Meet real, perfil pessoal ou captura de áudio.
- Commit de implementação: `362c63d2fc2b4c3ab4b7dd92e19833d907a843a7`.

## Task 4 — referências Meet até o worker

- Base: `d44e2d2093ad0bc43f1ff667c171e81f2b060e2b`.
- RED: `python -m pytest tests/test_fluxo_meet_ponta_a_ponta.py::test_parar_sela_e_entrega_refs_ao_job -v` exit 1; a parada real criou job com `eventos_refs=()` apesar de `EventStore.seal()` produzir um segmento.
- GREEN: mesmo teste exit 0; `python -m pytest tests/test_fluxo_meet_ponta_a_ponta.py tests/test_nomes_meet_worker.py tests/test_fila_processamento.py tests/test_processador_reuniao.py -v` exit 0, 21 passed; regressão do ciclo/bandeja exit 0, 16 passed; teste do limite de 500 linhas exit 0; `git diff --check` exit 0.
- Fluxo verificado: `_parar_transcricao()` e `_enfileirar_reuniao()` reais criam job v2 com refs; uma nova `FilaProcessamento` lê o job; `processar_job()` carrega o evento; hash adulterado resulta em `evento_hash_invalido_recusado` e nenhum nome. O teste legado v1 passa sem nome inventado. Dados, áudio e nomes usados são sintéticos.
- Commit de implementação: `d9e2e7f3a2d4b858077be877a247136d0eedf1c9`.

## Task 5 — resultado estruturado canônico

- Base: `76ddfcfba7715ed27e9f8eb9b433ea8dd0439b05`.
- RED: `test_worker_materializa_resultado_estruturado` exit 1 porque `segments_ref` apontava para `reuniao.txt`; `test_manifesto_com_json_malformado_nao_libera_retencao` exit 1 porque um hash válido bastava mesmo com campos de segmento ausentes.
- GREEN em 22/09/2026: `python -m pytest tests/test_resultado_pipeline.py tests/test_resultado_reuniao.py tests/test_processador_reuniao.py tests/test_retencao_resultado.py -v` exit 0, 25 passed; `python -m pytest tests/ -q --tb=short` exit 0, 720 passed; limite de 500 linhas e `git diff --check` exit 0.
- O worker grava `resultados/{job.id}.json`, deriva TXT do JSON, cria as refs e valida o manifesto antes de concluir. O alinhamento usa intervalo e texto, preserva origem e sinaliza `segment_alignment_failed` sem atribuir nome por índice. Saída existente é preservada e o job falha sem apagar o áudio. A API pública `retranscrever()` mantém retorno `str`.
- Commit de implementação: `3f505e736a98df4f268ec461d30044876186261b`.

## Task 6 — sugestões, proveniência e revisão

- Base: `9c4ddef2d2b634790a655524adb442cdbd0fb4c1`.
- RED: `serializar_atribuicao` ausente; worker gravava `assignment: null`; Playwright não mostrava sugestão nem atualizava revisão após 409; TXT editado fora do app permitia avançar revisão JSON antes de falhar. Todos reproduzidos por testes específicos.
- GREEN em 22/09/2026: `python -m pytest tests/test_identidade_reuniao.py tests/test_correlacionador.py tests/test_resultado_reuniao.py tests/test_resultado_pipeline.py tests/test_nomes_meet_worker.py -v` exit 0, 40 passed; `npm run test:e2e -- participants.spec.js` exit 0, 4 passed; limite de 500 linhas e `git diff --check` exit 0.
- Sugestões persistem com status, fonte, confiança, IDs de evidência e versão da calibração. TXT permanece pendente até confirmação manual. O drawer escapa texto/nome, exige escolha manual se o mesmo cluster tiver sugestões divergentes, recarrega a revisão em 409; confirmação e undo atualizam TXT e hashes do manifesto. Não há criação de perfil biométrico nesse fluxo.
- Commit de implementação: `ab330cf1a3ffa2bd48d909b72cbbb2cc0559af5c`.

## Task 7 — autenticação TKAS/1 e leitura incremental

- Base: `02bb011078fb13e7c1d969d06d5f0c1dd2e05802`.
- RED: `test_tkas_rejeita_sufixo_apos_chunk_final_cheio` aceitou bytes não autenticados depois de `TAG_FINAL`; `test_validacao_de_cifra_nao_acumula_chunks` mediu 100 objetos vivos no `list(...)`; inspeção de WAV cifrado com sufixo no segundo chunk retornou sucesso sem consumir o final.
- GREEN em 22/09/2026: `python -m pytest tests/test_crypto_stream.py tests/test_audio_streaming.py tests/test_audio_utils.py -v` exit 0, 20 passed; após remover parser RIFF não usado, gate dirigido exit 0, 20 passed; `python -m pytest tests/ -q --tb=short` exit 0, 726 passed; `git diff --check` exit 0.
- TKAS/1 exige chunk size fixo e EOF após a tag final. A validação de `encrypt_file` itera sem agregar plaintext; falha remove o temporário. `IteratorReader` mantém apenas o chunk atual; `wave.open` e inspeção consomem o stream cifrado inteiro sem tempfile plaintext. A suíte de áudio longo existente exercita 60 segundos sintéticos em blocos; gate físico de duração maior permanece na Task 12.
- Commit de implementação: `f6f11b9af2939c0bed660654482588057decff6f`.

## Task 8 — modo protegido para áudio e resultados

- Base: `c23a24b2ec66d03e028b77d3e24fb2c054e5e639`.
- RED: proteção de WAV produzia `.wav.enc` em vez de TKAS; resultado ainda gravava JSON aberto; job ignorava `_mic.tks`; primeira configuração omitia `protection_mode`; proteção dependia da flag legada; falha entre revisão e manifesto deixava estado inconsistente; diarização criava diretório temporário plaintext; retenção ignorava TKAS órfão. Cada comportamento foi reproduzido em teste antes da correção.
- GREEN em 23/09/2026, Windows/Python 3.12: `python -m pytest tests/ -q --tb=short -x` exit 0, 741 passed em 143,75 s; gate dirigido de storage/política/crypto/captura/retencão exit 0, 79 passed; `git diff --cached --check` exit 0.
- O modo protegido persiste na primeira configuração. Captura, microfone, órfãos e resultado usam TKAS/1, JSON cifrado e TKPT. Revisão e undo atualizam resultado e manifesto com trava e journal de rollback; leitura recusa hash/schema/path inválido. A diarização protegida percorre áudio cifrado sem criar WAV/TXT temporário em claro. O modo legado mantém leitura compatível.
- Durante a primeira suíte completa, um teste importou o app com a pasta real de áudio e converteu dois WAV órfãos preexistentes. O guard de estado detectou a mudança; ambos foram restaurados byte a byte aos caminhos originais e os dois TKAS criados pelo teste foram removidos. Os horários de modificação originais não eram recuperáveis. O fixture de importação passou a isolar as pastas do app; a suíte completa posterior terminou sem modificar o estado real.
- Gate físico de áudio e instalação permanece na Task 12. Commit de implementação: `863261d09e2a65b04ba353a7e21245a61133765c`.
- Complemento auditado em 24/09/2026: o menu mostrava o modo efetivo, mas não oferecia a escolha `protected` para instalações existentes; o assistente não tinha ação explícita de exportar TXT. RED: `pytest tests/test_assistente_mutacoes.py tests/test_politica_privacidade.py -q --tb=short` exit 1, três falhas por rota 404 e método ausente. GREEN: modo protegido ativado somente após confirmação, chave DPAPI disponível e captura/processamento ociosos; arquivos legados não são migrados. O assistente oferece download TXT em memória por POST autenticado, com confirmação e aviso de dados sensíveis, sem gravar TXT no servidor. Gate dirigido final: 45 passed (inclui manual e limite de linhas); Playwright dirigido: 1 passed; suíte completa: 804 passed. Commit de código: `8527b1ddaf5bda27b97d7857f3478ba1ef8b7111`. Gate de áudio real ainda pendente.

## Task 9 — privacidade de logs e mutações HTTP locais

- RED: título canário apareceu no sanitizador; cookie alcançava as rotas de correção, undo e chat sem Origin ou com outra porta; mutações sem JSON retornavam erro de negócio antes de validar Content-Type. Testes novos reproduziram as falhas. Canários adicionais revelaram mensagem de erro crítico, caminho completo na falha de exclusão de áudio e exceções do Whisper nos logs.
- Correção: linha de detecção emite código e fontes conhecidas; o filtro de status deixa de liberar textos por prefixo/`.txt`; erros e paths dos caminhos identificados são reduzidos a códigos operacionais. O guard comum valida Host local, Origin exatamente igual a esquema/host/porta e JSON em POST/PUT/PATCH/DELETE; ausência de Origin exige header secreto, não basta cookie.
- GREEN dirigido em worktree isolada em 23/09/2026: `python -m pytest tests/test_privacidade_eventos.py tests/test_ciclo_reuniao_sem_deadlock.py tests/test_assistente_mutacoes.py -q --tb=short -x` exit 0, 40 passed, com `TRANSKRIPTOR_ESTADO_REAL_ROOT` apontando à própria worktree. O teste anterior de dois logs do Whisper falhou no RED e passou após correção.
- Gate de privacidade/API em worktree isolada: `python -m pytest tests/test_status_seguro.py tests/test_privacidade_eventos.py tests/test_assistente_mutacoes.py tests/test_assistente_validacao.py tests/test_assistente_seguranca.py tests/test_token_sessao.py tests/test_assistente_api.py -q --tb=short -x` exit 0, 83 passed. `git diff --cached --check` exit 0 antes do commit.
- A instância real estava gravando e depois processando uma reunião durante a verificação; seus arquivos e processo foram preservados. O guard de estado do checkout principal detectou corretamente a atividade externa. A suíte completa na worktree chegou a 54% sem falha e foi interrompida pelo agente quando o worker real avançou para `transcribe`; este resultado parcial não conta como PASS. Regressão global após Task 9 permanece pendente até o worker ficar ocioso. Nenhum gate físico ou release foi inferido da worktree.
- Commit de implementação: `9737075d30045a3ae5671f0ec57cbccd167edae6`.

## Task 10 — dependências, CI e SBOM reproduzíveis

- Estado: implementação CPU e gate local DONE; CI remoto e instalação CUDA real PENDENTES para a Task 12. A exceção de segurança provisória exige aceite explícito antes de release.
- Base: `f8b92ccb0c40822c1d6df47af7a6f78f28936454`.
- Resultado: `d14ff2a293f100f408955c861f50de8b7f69d104`.
- RED: `tests/test_dependencias.py` falhou pela ausência de locks com hash, gerador e SBOM CycloneDX; `tests/test_instalador_helper.py` falhou porque o batch ainda instalava torch livre e constraints antigos. A reprodução de troca de rota e o subprocesso `--version` também falharam antes das correções.
- GREEN: Windows/Python 3.12, venv CPU temporária isolada: instalação com `pip install --require-hashes` dos locks CPU e dev exit 0; `pip check` exit 0; `python -m pytest tests/ -q --tb=short` exit 0, **778 passed** em 212,37 s, com `TRANSKRIPTOR_ESTADO_REAL_ROOT` na worktree de validação. `git diff --cached --check` exit 0 e `compileall` dos scripts alterados exit 0.
- SBOM: CycloneDX 1.6 com 62 componentes, 62 relações, 62 hashes SHA-256 e 61 licenças declaradas; duas gerações na mesma venv tiveram SHA-256 idêntico `DC20295403CFBE31BB37EB8B08A36620CAE1CE44F2AECB1746FA1A9A20E58E9C`.
- Auditoria: o primeiro `pip-audit` bruto encontrou 44 entradas em cinco pacotes; a atualização de cryptography, Flask e Pillow reduziu para três entradas em dois pacotes. `pip-audit --no-deps --disable-pip` com exceções restritas a `PYSEC-2026-3447` (setuptools/macOS sdist) e `PYSEC-2025-194` (torch.jit.script local) terminou exit 0, "No known vulnerabilities found, 3 ignored". Justificativas e prazo 15/10/2026 em `docs/DEPENDENCIAS.md`; CI falha após o prazo. Auditoria bruta permanece vermelha por essas duas exceções.
- Rota CUDA: lock deriva a árvore CPU e substitui apenas torch/torchaudio pelos hashes publicados dos wheels oficiais Windows cp312 cu128; os bytes do wheel CUDA e a instalação CUDA não foram verificados. O instalador agora usa somente o lock escolhido, recusa `.venv` de outra rota e valida as versões antes/depois.
- Regressão detectada: a primeira suíte completa na worktree terminou 772 passed/2 failed por `transcricao_core.py` ter 506 linhas após Task 9; a importação do emissor de evento foi centralizada, restaurando 500 linhas. Outra suíte terminou 777 passed/1 failed por asserção legada da versão no batch; a asserção foi atualizada e a chamada CLI testada, inclusive com caminho de Python contendo espaço. A suíte final de 778 passou. Nenhum desses resultados vermelhos foi contado como gate verde.
- A instância `pythonw.exe` do usuário e seus dados foram preservados. O job real observado passou a `ready/finalize`; nenhuma instalação em uso foi substituída. Não houve push nem CI remoto neste commit.

## Task 11 — aceite isolado de instalação e desinstalação

- Estado: implementação e gate CPU isolado DONE; abertura da bandeja real duas vezes PENDENTE para o gate físico da Task 12. O harness de instância não substitui essa prova.
- Base: `2abda86b29748bdff33e133f140040b8aa52001e`.
- Commit de implementação: `e8a6f2fd318bdeaa25ee1658b6a717c419c176cf`.
- RED: batch continha `rmdir`/`del` diretos; `test_batches_expoem_flags_seguras_sem_apagar_dados` exit 1. Teste de leitura da versão por `for /f` detectou comando com Python em caminho com espaços. Teste com `.lnk` COM real falhou porque a inspeção PowerShell não recebia o caminho; passou após envio por variável de ambiente.
- GREEN: `python -m pytest tests/test_gate_instalacao.py tests/test_instalacao_caminhos.py tests/test_instalador_helper.py tests/test_atalho_desktop.py tests/test_assistente_startup.py tests/test_versao.py -q --tb=short -x` exit 0, **45 passed** em 17,48 s, Windows/Python 3.12, com `TRANSKRIPTOR_ESTADO_REAL_ROOT` na worktree isolada. `compileall` dos scripts/teste novos exit 0; `git diff --cached --check` exit 0.
- Gate CPU: `python scripts/gate_instalacao.py --route cpu` exit 0 em pasta temporária exclusiva na unidade E:, com `TEMP`/`TMP` apontando para essa pasta e `PIP_NO_CACHE_DIR=1` no batch. Copiou 402 arquivos versionados, instalou pelo lock com hashes, executou `pip check` e validou a rota; criou atalho em Desktop falso, removeu `.venv` e atalho na desinstalação isolada. Os hashes SHA-256 dos três canários (`transcricoes`, `_modelo_voz`, `config_user.json`) permaneceram idênticos; `atalhos_reais_intocados=true`; PIDs filhos 97864 e 51156, porta local 51567. A pasta temporária foi removida e conferida ausente.
- Hashes dos canários no gate final: `transcricoes/canario.bin` `8a59fba50c6a3315ba7e6e391f5877a687c877064f9a6571d0d6d44bb6ee5992`; `_modelo_voz/canario.bin` `92f338befb36e4d41b90a4ce18d61f17b3ba202ef7f112920738e3fc2f5a2d31`; `config_user.json` `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`.
- Escopo da prova de instância: dois processos filhos executaram `transkriptor_lock.adquirir_lock` com lock de arquivo e porta local; a segunda aquisição foi recusada. Essa prova **não** inicializa `transkriptor.pyw`, o mutex nomeado global nem a bandeja/assistente. A instância do usuário (PID 16412) continuou ativa e não foi encerrada.
- Segurança: o modo isolado exige marcador com raiz resolvida e nonce efêmero do gate; alvos de remoção são caminhos exatos. O modo normal consulta a linha de comando de processos e falha fechado; só remove atalho que aponte para esta instalação. Exclusão de dados exige escolha explícita no batch. Testes sintéticos comprovaram preservação padrão, remoção seletiva e recusa de processo ativo. O primeiro gate em C: foi interrompido por pouco espaço; sua pasta temporária foi removida. A rodada final em E: passou sem tocar na instalação em uso.

## Task 12 — automação e fechamento ainda em execução

- Base documental: `60bd0ec8430d5e690906ff88fc25e2e72157e2ff`. Estado: IN_PROGRESS; nenhum bump ou release.
- Step 1 em 23/09/2026, Windows/Python 3.12, estado de teste isolado: `python -m pytest tests/ -q --tb=short` exit 0, **792 passed** em 203,22 s; `python scripts/verificar_fase.py --fase all` exit 0, rastreabilidade OK e **237 passed** em 52,38 s; `python -m compileall -q .` exit 0; `npm ci` exit 0, 84 pacotes auditados e zero alertas npm; `npm run test:unit` exit 0, **22 passed**; `npm run test:e2e` exit 0, **20 passed**; `python -m pip check` exit 0 na venv CPU, sem requisitos quebrados; `git diff --check` exit 0. Uma primeira chamada do verificador sem variável de isolamento foi interrompida pelo agente após cerca de 10% e não conta como gate; o comando completo com isolamento passou. A instância real PID 16412 permaneceu ativa e o checkout limpo antes da atualização documental.
- Manual: `tests/test_manual_usuario.py::test_manual_atual_descreve_locks_e_modo_protegido` confirmou RED exit 1 por ausência do lock e proteção no texto. Após atualização inicial do Markdown/PDF, `python -m pytest tests/test_manual_usuario.py -q --tb=short -x` exit 0, **5 passed**. O texto foi complementado com o menu de proteção e a exportação TXT; o PDF final tem 8 páginas e 20.834 caracteres extraíveis, e os 5 testes passaram novamente. As 8 páginas foram renderizadas e inspecionadas em folha de contato; após a última linha de configuração, a página 5 foi inspecionada novamente, sem corte aparente. Falta gate no SHA documental.
- Evidências históricas `T-13.*.md`: placeholders de commit substituídos por SHAs retornados por `git log -1 -- <arquivo>`; todos os SHAs de base/resultado inspecionados existem no Git. A base de G1 foi corrigida de `62abbc0` para seu pai real `2eaf41f`; os outros 24 arquivos já tinham base igual ao pai do primeiro resultado. Os estados históricos permanecem descritos como históricos; G1/G2 têm bloqueios atuais explícitos.
- Gates restantes: CI remoto do mesmo SHA após push autorizado; captura real 25/600 s com aplicativo ocioso; D2 em Chrome e Edge com perfis temporários; G3 com três pessoas consentidas; CUDA real e duas partidas da bandeja; aceite explícito das exceções temporárias de dependências; só então bump, suíte pós-bump, release e sincronização Git. O usuário informou que preparará a janela e participantes depois. Nenhum gate físico foi inferido dos testes automatizados.
- Repetição após o complemento de código `8527b1ddaf5bda27b97d7857f3478ba1ef8b7111`, em 24/09/2026: suíte Python **804 passed** (exit 0, 118,24 s), `verificar_fase.py --fase all` rastreabilidade OK e **238 passed** (exit 0, 32,63 s); `compileall -q .` exit 0; `npm ci` exit 0, 84 pacotes auditados e zero vulnerabilidades npm; Vitest **22 passed** exit 0; Playwright **21 passed** exit 0; `pip check` exit 0; `git diff --check` exit 0. Todos os testes Python usaram `TRANSKRIPTOR_ESTADO_REAL_ROOT=C:\Projetos\transkriptor-task9-validation` para isolar dados reais. O PDF final regenerado tem 20.834 caracteres extraíveis e o teste do manual passou. Estes são gates automatizados; CI remoto e gates físicos continuam pendentes.
