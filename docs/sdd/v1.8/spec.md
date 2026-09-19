# Spec — Transkriptor v1.8 proposta

Fonte de versão do produto: `config.VERSAO`. IDs novos usam série 13, pois a release 1.7 já referencia FR-12.A1. Aprovar esta spec não marca tarefas como executadas.

As assinaturas normativas e formatos planejados estão em `interfaces.md`; o protocolo de execução e interpretação está em `executor-llm.md`. Divergência descoberta durante TDD exige emenda explícita nos três documentos antes de código incompatível.

As decisões DU-01–DU-16 em `decisoes-usuario.md` foram aprovadas e fazem parte desta spec. A–G não possuem decisão de produto pendente. Tipo/edição da conta e autorização Google continuam ausentes e bloqueiam somente H.

## Invariantes globais

- Python 3.12+; texto UTF-8 e interface PT-BR; constantes em `config.py`.
- Reutilizar `transcricao_core.Transcritor`; nenhum callback de status sob lock do ciclo.
- Serviços do aplicativo em `127.0.0.1`; IA local por padrão; conector Google opcional e explícito.
- Áudio, transcrição e biometria nunca saem do dispositivo; Google opcional acessa apenas metadados/artefatos oficiais autorizados.
- Não gravar antes de consentimento positivo. Sem captura silenciosa de reuniões de teste.
- Testes usam diretórios temporários e logs isolados; não importar `transkriptor` na coleta.
- Não apagar originais, mudar preferências privadas ou migrar biometria sem o fluxo específico descrito.
- Toda task termina com teste específico, regressão e evidência. Falha bloqueia avanço.

## Requisitos e rastreabilidade

| Requisito | Comportamento verificável | Tarefa |
|---|---|---|
| NFR-13.A1 | Uma versão/referência SDD ativa e mapa release→spec→tasks→evidência; legado identificado como histórico; gates não inferem sucesso por contagem mínima de testes. | T-13.A1 |
| NFR-13.A2 | Gate de áudio rejeita só cabeçalho/silêncio/nenhuma fala; runner executa JS real; harness isola arquivos, subprocessos e relógios. | T-13.A2 |
| FR-13.B1 | Claim e alterações de job são exclusivas entre processos; lease identifica PID + instante de criação + nonce; recuperação não toma trabalho de proprietário vivo. | T-13.B1 |
| FR-13.B2 | Retenção depende de manifesto de resultado válido, hash e nenhum job ativo/pendente/reprocessamento; cabeçalho ou arquivo parcial nunca libera exclusão. | T-13.B2 |
| FR-13.B3 | Progresso e timeout de inatividade por etapa; falha deixa áudio preservado e permite próximo job; retry limitado, cancelamento explícito e erro visível. | T-13.B3 |
| FR-13.C1 | Watchdog mede avanço de frames por loopback/mic, diferencia silêncio de falha, detecta dispositivo perdido/disco cheio e cobre COM no cadastro de voz. | T-13.C1 |
| FR-13.C2 | STT cobre fala exclusiva do mic e do loopback, com alinhamento por fonte e deduplicação de eco; leitor de mic aceita WAV cifrado; sobreposição é preservada. | T-13.C2 |
| NFR-13.C3 | Leitura por blocos, PCM validado, tempo relativo baseado no sample rate real e resampling explícito; limite de RAM inclui decifragem e diarização. | T-13.C3 |
| FR-13.D1 | Cada evento pertence a session_id/connection_id/tab_id/meeting_key e sequência; eventos antigos, de outra sessão ou fora do intervalo consentido são recusados. | T-13.D1 |
| SEC-13.D2 | Content script não armazena segredo de conexão; service worker valida sender e sessão; bridge valida origem exata, token/pareamento, tamanho, tipo e frequência. | T-13.D2 |
| FR-13.D3 | Roster e legenda têm parser versionado testado no JS de produção; tile visível não prova fala; homônimos e indisponibilidade de seletor são explícitos. | T-13.D3 |
| SEC-13.D4 | Eventos autorizados são persistidos por sessão em armazenamento cifrado, drenado continuamente e com limites; overflow é sinalizado; job/log não contém legenda, nomes ou embeddings. | T-13.D4 |
| FR-13.D5 | Worker recebe referências de eventos, alinhamento e preferências congeladas no consentimento; restart preserva o contrato e a atribuição. | T-13.D5 |
| FR-13.D6 | Resolver mantém pessoa/cluster separados; combina texto, tempo e identidade; empate, relógio incerto, sobreposição e sinal fraco produzem pendência, não nome arbitrário. | T-13.D6 |
| FR-13.D7 | Resultado contém roster, segmentos, proveniência, confiança e estados das etapas; revisão altera reunião escolhida e exportações, com undo e sem cadastrar voz implicitamente. | T-13.D7 |
| SEC-13.E1 | Políticas compatível/protegida explícitas; falha de cifra não vira êxito; não sobrescrever chave ilegível nem remover original antes de validar cópia equivalente. | T-13.E1 |
| SEC-13.E2 | Todos os artefatos temporários/ativos pertencem a sessão; recuperação cobre raiz legada e diretórios temporários, sem tocar sessões vivas ou apagar a única cópia. | T-13.E2 |
| SEC-13.E3 | API exige objeto/tipos/limites efetivos, origem/host aceitos, headers de privacidade e limite de concorrência; cancelamento fecha upstream e status parcial é explícito. | T-13.E3 |
| SEC-13.E4 | Logs aceitam eventos tipados com campos permitidos; sem conteúdo/tokens/nomes por padrão; consentimento de biometria é separado, revogável e com remoção verificável. | T-13.E4 |
| UX-13.F1 | Conversa/histórico pertencem a meeting_id; troca/limpeza durante streaming não mistura respostas; janela de histórico é limitada por mensagens e orçamento. | T-13.F1 |
| FR-13.F2 | Respostas apontam segmentos e distinguem ausência/contradição; orçamento inclui entrada/histórico/saída; redução recursiva limitada e cancelável; fala é dado não confiável. | T-13.F2 |
| UX-13.F3 | Lista paginada com índice de metadados, atualização após job; busca, drawer, foco, teclado, contraste e clipboard verificados em navegador. | T-13.F3 |
| NFR-13.G1 | Dependências reproduzíveis por plataforma, matriz CPU/CUDA, auditoria de CVEs/SBOM e CI Windows com Python+JS; sem falso sucesso em ambiente global contaminado. | T-13.G1 |
| NFR-13.G2 | Instalar/iniciar/desinstalar em caminho com espaço/acentos; todos os entrypoints usam ambiente correto, versão dinâmica e autenticação utilizável. | T-13.G2 |
| NFR-13.G3 | Release só com corpus rotulado, métricas publicadas, gates físicos e regressões; documentação, versão, artefatos e evidências correspondem ao mesmo commit. | T-13.G3 |
| FR-13.H1 | Conector Google opcional detecta capacidade e papel, OAuth mínimo, revogação e erro de permissão; indisponibilidade não bloqueia modo local. | T-13.H1 |
| FR-13.H2 | Importação pagina participantes/sessões/entries, lida com múltiplas transcrições, expiração e reentrada, preserva fonte e não atribui voz só pela lista de presentes. | T-13.H2 |
| NFR-13.H3 | Media API só avança após teste de elegibilidade e documento de decisão; track/CSRC, consentimento, suspensão e restrições são demonstrados em piloto separado. | T-13.H3 |

## Contratos propostos

Os nomes abaixo são contratos para a implementação, não APIs já existentes.

```python
# sessao_reuniao.py
@dataclass(frozen=True)
class SessaoReuniao:
    session_id: str             # UUID local, nunca o nome da pessoa
    meeting_key: str            # identificador opaco por conferencia/instancia
    consented_at_utc: str
    first_frame_monotonic_ns: int | None
    policy_id: str

# identidade_reuniao.py
@dataclass(frozen=True)
class Atribuicao:
    participant_id: str | None
    display_name: str | None
    source: str                # manual, google_entry, caption, voice, unknown
    score: float | None         # escore calibrado; nao chamar probabilidade sem validacao
    evidence_ids: tuple[str, ...]
    status: str                # confirmed, suggested, unknown, conflict
```

Envelope de evento `schema_version=1`: `event_id`, `session_id`, `connection_id`, `seq`, `tab_id`, `meeting_key`, `kind`, `client_wall_ms`, `client_monotonic_ms`, `received_monotonic_ns`, `participant_id?`, `display_name?`, `caption_id?`, `caption_revision?`, `text?`, `confidence_source`. `kind` pertence a `heartbeat|participant_join|participant_leave|caption|speaker_activity|capabilities`.

Relógios: registrar handshake com ida/volta e amostras de offset; recalibrar na reconexão. Duração de áudio usa frames/sample rate. Se incerteza do alinhamento >1,5 s, não aplicar nome por tempo sozinho. Não usar `Date.now() - instante anterior ao start()` como única origem temporal.

`eventos_meet_store.EventStore(root, session, cipher)` expõe `append(event) -> ack_seq`, `read_events() -> Iterator[dict]`, `seal() -> ArtifactRef`. ACK só após persistência durável. `ArtifactRef` contém caminho relativo, formato, versão, SHA-256 e tamanho; paths sempre resolvidos dentro da raiz da sessão.

Job v2 preserva leitura de v1 e acrescenta `schema_version`, `session_id`, `artifact_refs`, `capture_metrics`, `stage`, `lease`, `attempt`, `warnings`. Referências sensíveis não carregam o conteúdo. Worker valida hash/formato antes de abrir artefato e escreve `ResultManifest` atomicamente antes de marcar `ready`.

`ResultManifest`: `meeting_id`, `schema_version`, `source_audio_hashes`, `participants_ref`, `segments_ref`, `stage_status`, `warnings`, `exports`, `created_at`, `pipeline_version`. Segmento: `segment_id`, `start_ms`, `end_ms`, `audio_source`, `text`, `speaker_cluster_id`, `assignment`, `overlap`. Resultado parcial é utilizável, mas não libera retenção automática da única fonte necessária.

Estados de job: `pending`, `processing`, `ready`, `failed`, mais `cancelled`; qualidade por etapa em `stage_status` (`complete|partial|failed|skipped`). `ready` exige resultado íntegro, sem afirmar que todas as identificações são conhecidas.

## Limites e metas propostas

- Ponte: máximo 4 KiB por envelope; 20 eventos/s sustentados, burst 40 por conexão; limitar conexões autenticadas a 4. Agregar revisões/heartbeats sem perder a última versão; excesso gera contador e aviso, não descarte invisível.
- Buffer em RAM: 500 eventos drenados a cada ≤1 s; spool cifrado por sessão até 256 MiB. Esgotamento marca identificação parcial; não para nem apaga áudio.
- Health: sem avanço de frames durante 10 s com captura ativa → erro visível; silêncio com frames avançando não dispara falha. Prazo validado com fakes de relógio e hardware.
- Worker: heartbeat a cada 5 s; etapa sem progresso 120 s → aviso; 600 s sem progresso → falha controlada/retry até 2 tentativas, considerando inicialização de modelo separadamente. Configurável e não baseado só no tempo total da reunião.
- Corpus mínimo: 12 sessões consentidas, ≥180 minutos, ≥12 vozes, pelo menos 300 turnos avaliáveis; pelo menos 6 sessões reservadas para teste, separadas por reunião e por falantes quando possível.
- Precisão nominal seletiva obrigatória ≥98% dos turnos automaticamente nomeados; cobertura ≥80% nos turnos com evidência utilizável; reportar também cobertura sobre TODOS os turnos, abstinências e IC 95%. Não inflar precisão omitindo erros. Se amostra não sustenta meta, manter `suggested`/`unknown` e mostrar `Identificação pendente`.
- Fala exclusiva do mic: ≥95% dos turnos de teste presentes; medir WER por fonte, DER com política de sobreposição declarada e duplicação por eco ≤1% dos turnos avaliados. Meta não substitui revisão dos casos difíceis.
- Recursos: captura sem IA com CPU média <10% e crescimento de memória <100 MiB em 10 min no hardware de referência registrado; pós-processamento tem orçamento separado. Leitura de áudio deve usar blocos ≤30 s; teste de 2 h não pode materializar waveform completo. Medir pico real do worker antes de fixar limite absoluto de RAM.
- UI: 375/860/1366 px, teclado completo, foco restaurado no drawer e contraste AA; consulta paginada de 1.000 metadados com p95 <1 s no hardware de referência. Sem decifrar todos os textos para listar.

## Política de privacidade, retenção e compatibilidade

Instalação existente sem preferência de política permanece em modo compatível, mantém TXT legível e informa o que está cifrado. Instalação nova começa protegida, exporta TXT somente mediante ação e mantém resultado/eventos/perfis cifrados. Migração começa em dry-run, verifica hashes/conteúdo equivalentes e só remove a lista exata confirmada pelo usuário. Cópia cifrada antiga válida não prova equivalência com versão plaintext mais recente.

Legendas/nomes só são coletados após consentimento e ativação da função; heartbeat de detecção sem conteúdo pode anteceder a captura. Perfil de voz começa desligado, exige opt-in separado e permanece até revogação verificável. Áudio só é elegível para exclusão sete dias após resultado válido e ausência de trabalho dependente. Eventos Meet brutos só são elegíveis sete dias após resultado válido. Transcrições/resultados permanecem até exclusão manual. Nenhum teste usa pessoas reais sem autorização específica para aquele gate.

## Saída nominal aprovada

JSON estruturado é canônico. Exportação TXT usa uma linha por segmento: `[HH:MM:SS] Nome: texto`. Quando não houver atribuição qualificada, `Nome` é literalmente `Identificação pendente`. Correção manual cria nova revisão, pode ser desfeita e não cadastra perfil de voz.
