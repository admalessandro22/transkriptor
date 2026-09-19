# Diagnóstico de qualidade, consistência, confiabilidade e segurança

Data de fechamento: 19/09/2026. Referência de código: `eff83a61f3ee2291e48a80a00da3f70f1475ccbc`.

## Parecer

O Transkriptor tem uma base funcional de captura local, consentimento, processamento posterior e proteção de arquivos cifrados. Contudo, não há evidência suficiente para considerar o fluxo completo de identificação nominal confiável. Há defeitos concretos de integração que a suíte atual não detecta.

Prioridade de produto: **P1** antes de confiar reuniões importantes ao recurso; **P2** na mesma evolução, após integridade; **P3** extensão opcional. Essas prioridades não são severidades de vulnerabilidade. Não foi demonstrado comprometimento remoto crítico.

Classificação da evidência: **confirmado por código**, **reproduzido isoladamente**, **risco de arquitetura** ou **validação pendente**. Uma hipótese não equivale a incidente observado.

## O que já funciona como proteção

- Consentimento afirmativo antes da captura automática, recusa/erro conservadores e verificação de pausa: `app_ciclo_reuniao.py:214`.
- Núcleo `Transcritor` compartilhado; modo posterior evita carregar Whisper durante a gravação: `app_ciclo_reuniao.py:84`, `transcricao_core.py:328`.
- Contexto COM nas threads principais de loopback/microfone; regressões de callbacks e deadlock na suíte.
- Jobs com IDs restritos, paths contidos e escrita por temporário + `fsync` + `replace`: `fila_processamento.py:74`, `fila_processamento.py:108`.
- API do assistente exige token, usa cookie HttpOnly/SameSite Strict e valida realpath: `assistente.py:46`, `assistente.py:66`, `assistente.py:132`.
- AES-GCM e chave protegida por DPAPI para os artefatos cifrados: `crypto_storage.py:63`, `crypto_storage.py:178`.
- Colisões de nomes já têm tratamento sequencial: `crypto_storage.py:275`; não se deve apresentar colisão por precisão de minuto como defeito genérico sem considerar esse controle.
- Testes isolam logs e verificam preservação de estado local. Suíte executada: **520 passed em 120,59 s**.

## Achados e melhorias

| ID | Prioridade / evidência | Fragilidade e consequência | Evidência principal | Tarefa |
|---|---|---|---|---|
| D01 | P1 · código | Eventos Meet atribuídos ao capturador não são persistidos no job nem repassados ao novo Transcritor do worker. Nomes deixam de chegar à diarização normal. | `app_ciclo_reuniao.py:169`; `app_processamento.py:163`; `processador_reuniao.py:54`; `retranscritor.py:254` | D4–D5 |
| D02 | P1 · código | Whisper transcreve só o loopback. Mic é usado para reforçar rótulo de segmentos existentes, sem recuperar falas exclusivas do usuário. | `retranscritor.py:210`; `retranscritor.py:264`; `diarizador.py:175` | C2 |
| D03 | P1 · reprodução | Fila Meet guarda no máximo 500 eventos e só é drenada ao parar. Ensaio com 600 reteve os primeiros 500 e descartou 100 finais. A 1 evento/1,5 s, enche em aproximadamente 12,5 min; mutações podem acelerar isso. | `meet_bridge.py:99`, `meet_bridge.py:138`; `extension/meet/content.js:249` | D4 |
| D04 | P1 · reprodução | Uma legenda sem palavras em comum ainda entra no fallback por frequência e pode substituir `VOCÊ`. Nome incorreto pode aparecer com aparência de certeza. | `correlacionador.py:33`, `correlacionador.py:126`, `correlacionador.py:152` | D6 |
| D05 | P1 · código | “Falante ativo” pode ser simplesmente o primeiro tile com opacidade >0,5, inclusive sem verificar se está falando. | `extension/meet/content.js:203` | D3 |
| D06 | P1 · código/pendente | Há um único estado global de reunião, sem ID de conferência/aba nos eventos. Duas abas e eventos atrasados podem misturar estado, título e participantes. | `meet_bridge.py:105`, `meet_bridge.py:124`; `extension/meet/content.js:49` | D1 |
| D07 | P1 · código/pendente | Origin é validado por prefixo; `https://meet.google.com` é recusado e `http://localhost.example.test` aceito pela função. Token continua obrigatório. O Origin real emitido pelo content script não foi medido. | `meet_bridge.py:80`, `meet_bridge.py:181`; `extension/meet/content.js:59` | D2 |
| D08 | P1 · código | Rename depende de centroides em `app.transcritor`; captura é descartada do app no fim e o worker não devolve centroides. A correção nominal não está vinculada ao resultado persistido. | `transkriptor_menu_flows.py:348`; `app_ciclo_reuniao.py:179`; `retranscritor.py:254` | D7 |
| D09 | P1 · risco | `threading.Lock` não serializa processos. Pai registra PID e worker altera estado no mesmo JSON por read-modify-write; pode haver atualização perdida. Recuperação retorna todo `processing` a `pending` sem validar proprietário vivo. | `fila_processamento.py:72`, `fila_processamento.py:271`, `fila_processamento.py:316`; `app_processamento.py:69` | B1 |
| D10 | P1 · código | Retenção testa existência de TXT/TKPT, não resultado útil/validado nem estado do job. Captura já cria cabeçalho; worker escreve TXT antes da diarização. Um áudio antigo ainda necessário pode ficar elegível. | `retencao_audio.py:30`, `retencao_audio.py:85`; `transcricao_core.py:156`; `retranscritor.py:242` | B2 |
| D11 | P1 · código | `worker.wait()` não tem orçamento de inatividade; worker vivo travado bloqueia a fila serial. | `app_processamento.py:94` | B3 |
| D12 | P1 · código | Watchdog confere vida de threads, não avanço de frames; captura pode repetir erro e continuar viva. Mic não integra a verificação. Cadastro de perfil usa soundcard sem contexto COM próprio. | `watchdog.py:46`; `transcricao_core.py:206`; `captura_leve.py:46`; `identificador_voz.py:110` | C1 |
| D13 | P1 · código | Mic preservado como `.wav.enc` é passado ao leitor `wave.open` de trechos, sem decifragem nesse caminho; pode inviabilizar diarização com identificação ativa. | `retranscritor.py:264`; `diarizador.py:175`; `audio_utils.py:17` | C2 |
| D14 | P1 · código | Criptografia solicitada pode degradar para WAV/NPZ/JSON legível quando a chave está indisponível; cadastro pode anunciar sucesso. Não se aplica ao TXT principal intencional. | `identificador_voz.py:22`, `identificador_voz.py:47`, `identificador_voz.py:211`; `crypto_storage.py:412`, `crypto_storage.py:429` | E1 |
| D15 | P1 · código | WAV em gravação está na raiz; retranscrição recria WAV temporário em `diarizacao_*`. Recuperação automática só percorre `audio/*.wav`. Queda abrupta pode deixar áudio legível fora da recuperação. | `transcricao_core.py:173`; `retranscritor.py:245`; `crypto_storage.py:434` | E2 |
| D16 | P1 · código | Gate de reunião considera linhas de metadados e marcador “nenhuma fala reconhecida” como conteúdo. Também não exercita mic, nomes ou diarização. Passar nele não prova compreensão da fala. | `scripts/gate_reuniao_real.py:98`, `scripts/gate_reuniao_real.py:170`, `scripts/gate_reuniao_real.py:194` | A2, G3 |
| D17 | P2 · código | Testes da extensão usam parser Python espelhado; uma camada contém `pass`. Não executam o JS de produção, reconexão, DOM real ou service worker. | `tests/test_extensao_parsing.py:1`; `extension/meet/content.js:11` | A2, D2–D3 |
| D18 | P2 · código | Histórico global não é limpo/particionado ao trocar transcrição. O cliente acumula mensagens; a API recusa acima de 20, bloqueando a 12ª pergunta após 11 respostas, se não houver limpeza. | `static/assistente.js:34`, `static/assistente.js:453`, `static/assistente.js:539`; `assistente.py:219` | F1 |
| D19 | P2 · código | JSON não objeto e itens de histórico não objeto podem gerar 500; limite é verificado apenas pelo Content-Length. Não há contrato tipado de entrada nem orçamento global de chamadas. Token reduz exposição. | `assistente.py:204`; `assistente_ollama.py:161` | E3 |
| D20 | P2 · código | Resumos parciais são concatenados sem redução recursiva limitada; orçamento não inclui todo histórico/pergunta/resposta. Conteúdo transcrito está no system prompt; há risco de confusão entre dados e instruções. Não há ferramentas de execução no assistente inspecionado. | `resumo_longo.py:48`; `assistente_ollama.py:126`, `assistente_ollama.py:152` | F2 |
| D21 | P2 · código | Áudio completo é lido/decifrado em RAM; diarização escreve outra cópia. PCM diferente de 16 bits cai num tratamento genérico de 8 bits; duração de WAV cifrado presume header fixo. | `retranscritor.py:23`, `retranscritor.py:56`, `retranscritor.py:245`; `crypto_storage.py:425` | C3 |
| D22 | P2 · código | Listagem do assistente lê/decifra todas as transcrições; busca e alguns gates visuais são verificações de strings. Falta evidência de teclado/foco/leitor de tela no fluxo completo. | `assistente.py:158`; `static/assistente.js:238`; `tests/test_v16_c_a11y.py` | F3 |
| D23 | P2 · código | Sanitização de log distingue sistema por prefixos e substrings; não é uma separação estrutural entre conteúdo e evento operacional. Títulos também entram em status/metadados. | `status_seguro.py:56`; `app_ciclo_reuniao.py:110` | E4 |
| D24 | P2 · medido/código | Ambiente Python global tem conflito de dependências de outro pacote; requisitos do produto têm intervalos amplos e não há CI rastreado em `.github`. `websockets>=12` permite versões com API diferente da usada (`websocket.request`). | `requirements.txt`; `pyproject.toml`; `meet_bridge.py:182`; `pip check` | G1 |
| D25 | P2 · código | Instalador expande `%VENV_PY%` sem aspas em várias chamadas; quebra em caminhos com espaços. CLI/standalone divergem: `iniciar.bat` não muda cwd; assistente standalone abre URL sem token. | `instalar.bat:33`; `iniciar.bat`; `assistente.py:255`; `transcrever_meet.py:12` | G2 |
| D26 | P2 · código | Versão executável é 1.7.0, AGENTS aponta execução de tasks v1.5 e referência v1.6; planos antigos ainda dizem preview. Manual diverge sobre query token e ativação da ponte. | `AGENTS.md:17`; `config.py:10`; `docs/sdd/v1.6/plan.md:3`; `docs/MANUAL-USUARIO.md:273` | A1 |
| D27 | P2 · lacuna | Não há corpus avaliado de nomes/vozes com precisão, cobertura, WER/DER e cenários de sobreposição. Limiares numéricos e teto de 12 clusters não demonstram acurácia. | `config.py:88`; `correlacionador.py:13`; `diarizador.py:315` | D6, G3 |
| D28 | P3 · pesquisa | APIs Google podem enriquecer a identificação, mas dependem de conta, autorização e artefatos existentes. Lista de participantes sozinha não atribui voz. | `pesquisa-meet.md` | H1–H3 |

Todos os sufixos da coluna Tarefa se referem a `T-13.<sufixo>`.

## Segurança: impacto e contraprovas

**Proteção em repouso degradada (D14).** Acesso a uma cópia de WAV/biometria legível passa a dispensar a chave, se a operação ocorreu durante falha de DPAPI/cifragem. A exposição depende de acesso ao disco, backup ou pasta compartilhada; ACLs não foram auditadas. Severidade técnica conservadora: baixa; prioridade de correção P1 porque envolve dados sensíveis e estado de proteção pouco visível. Nunca apagar áudio para “resolver” uma falha de cifra: preservar em local restrito, informar o estado e retentar de forma controlada.

**Temporários de áudio após crash (D15).** A saída normal remove a pasta temporária, mas encerramento abrupto não executa a limpeza. A recuperação atual não a alcança. Mesmo pré-requisito de acesso aos arquivos, sem alegação de exposição pela internet. Severidade conservadora: baixa, prioridade P1. Solução: armazenamento por sessão, inventário de artefatos e recuperação que distingue arquivo ativo, órfão e resultado confirmado.

**Origin permissivo (D07)** é uma lacuna de defesa, não um bypass de autenticação demonstrado: o token continua necessário. Não foi encontrado fundamento para afirmar RCE, invasão remota ou acesso anônimo às transcrições nas rotas examinadas. Isso não certifica sua ausência no restante do produto/dependências.

**TXT legível** está explicitamente previsto na spec v1.5 e no menu “Criar cópia criptografada”. A proposta preserva a escolha existente e acrescenta um modo protegido opcional. Não atribui retroativamente uma garantia de cifra integral que o produto não oferece.

**Nome exibido não é identidade verificada.** Pessoas podem compartilhar computador, usar apelidos ou nomes iguais. Guardar um identificador de participante quando disponível, origem da atribuição, evidência e incerteza. Perfil de voz persistente exige tratamento próprio: dado biométrico vinculado a pessoa natural é sensível na LGPD; o clique do operador para gravar não resolve sozinho a base legal aplicável a todos os participantes. Definir finalidade, base legal, transparência, retenção e atendimento dos titulares com o responsável pelo uso. [LGPD, arts. 5, 6, 7, 11 e 18](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm).

## Limites da conclusão

Foram examinados os principais caminhos de captura, extensão, identificação, fila, persistência, API, assistente, instalação e testes. Não foram abertos áudios/transcrições reais, perfis biométricos, credenciais nem logs privados. Não houve gravação, reinício do aplicativo, alteração de configuração, instalação de dependências ou acesso a uma reunião.

Dois revisores independentes atingiram limite de uso antes do relatório final. Seus apontamentos aproveitados foram conferidos no código pelo agente principal; a revisão independente de arquitetura foi concluída. A auditoria de segurança declara **cobertura parcial do inventário total**, sem revisão integral de todo código auxiliar/legado, bibliotecas, binários e modelos. Também não houve varredura atual de CVEs, pentest, auditoria de ACLs ou teste físico de longa duração. Essas verificações estão incluídas nos gates propostos; não se deve marcar a plataforma como certificada ou pronta para produção a partir deste documento.
