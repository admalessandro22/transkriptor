# Identificação de participantes do Google Meet — pesquisa e decisão

Fontes oficiais consultadas em 18–19/09/2026. Disponibilidade de APIs, edições e políticas deve ser reconferida antes da integração. “Nome” significa nome apresentado pelo serviço ou confirmado pelo usuário; não identidade civil certificada.

## Duas necessidades diferentes

1. **Quem participou?** Uma lista de participantes pode trazer nome e identificador.
2. **Quem disse cada frase?** É necessário ligar um trecho de áudio/texto a um participante. Lista de presentes, convite de Calendar e ordem dos tiles não estabelecem essa ligação.

Whisper reconhece fala e diarização agrupa vozes; nenhum dos dois conhece automaticamente o nome de uma pessoa desconhecida. É preciso uma fonte externa de identidade ou confirmação humana.

## Alternativas

| Caminho | O que entrega | Condições / limitações | Adequação ao produto |
|---|---|---|---|
| Extensão local lendo participantes e legendas | Nome exibido + legenda/estado observável durante a chamada | DOM muda; depende de legenda disponível, permissões do navegador e validação de seleção; não há contrato oficial do DOM do Meet | Principal recomendado, aproveitando código existente e mantendo processamento local |
| Meet REST API — participants / participantSessions | Participantes e sessões, inclusive entradas/saídas | OAuth e acesso ao conference record; nome não prova autoria de cada trecho | Complemento para roster e IDs; não substitui diarização |
| Meet REST API — transcripts.entries | Texto com `participant`, `startTime`, `endTime`, idioma | Precisa haver transcrição nativa gerada e acesso permitido; disponibilidade depende de edição/configuração | Melhor associação oficial entre texto e participante quando disponível |
| Meet Media API | Mídia em tempo real e informações para resolver origem dos streams | Prévia, escopos restritos, elegibilidade, consentimento e restrições de participantes | Experimento separado; não bloquear a entrega local |
| Perfis de voz locais confirmados | Sugestão por comparação de embeddings | Pessoa previamente cadastrada, calibração e gestão de biometria; desconhecidos continuam sem nome | Complemento opcional, desativado até consentimento específico |
| Correção pelo usuário | Atribuição explícita e revisável | Requer revisão humana; deve alterar resultado selecionado sem treinar perfil automaticamente | Fallback obrigatório |

### Participantes pela API oficial

O Google documenta um recurso por participante e sessões por combinação participante/dispositivo/entrada. Os tipos signed-in, anônimo e telefone expõem `displayName`; usuários autenticados também podem ter ID. Não tratar `displayName` como chave única. [Participantes e sessões](https://developers.google.com/workspace/meet/api/guides/participants).

O acesso usa OAuth em nome de um usuário, respeitando suas permissões. Para a proposta inicial, pedir somente `https://www.googleapis.com/auth/meetings.space.readonly`; não solicitar Drive completo nem delegação de domínio como pré-requisito. Escopos adicionais só se uma função concreta exigir e com consentimento separado. [Autenticação e escopos](https://developers.google.com/workspace/meet/api/guides/authenticate-authorize).

### Texto associado ao falante

`conferenceRecords.transcripts.entries` fornece referência `participant`, texto e início/fim. Essa relação pode ser usada para importar uma transcrição já nomeada ou como evidência adicional para alinhar trechos locais. Não substituir silenciosamente a transcrição Whisper por outra fonte. [Contrato TranscriptEntry](https://developers.google.com/workspace/meet/api/reference/rest/v2/conferenceRecords.transcripts.entries).

A documentação informa retenção de **30 dias para as entries da API** após o fim da reunião; arquivos no Drive seguem retenção própria. Tratar ausência, expiração e divergência entre Docs editado e entries sem fabricar dados. [Artefatos e retenção](https://developers.google.com/workspace/meet/api/guides/artifacts).

A transcrição nativa tem suporte a português e está listada para edições como Business Standard/Plus, Enterprise e algumas ofertas Education/Individual. Ativar legendas ao vivo não equivale a gerar esse artefato. A edição e o papel do usuário precisam ser verificados na conta real; não prometer disponibilidade para toda conta gratuita. [Disponibilidade da transcrição nativa](https://support.google.com/meet/answer/12849897).

Eventos do Workspace podem avisar início/fim, entrada/saída e geração de transcrição. Não são eventos palavra a palavra de quem está falando. Para um app local, consulta após reunião pode ser mais simples do que manter infraestrutura de assinatura. [Eventos Google Meet](https://developers.google.com/workspace/events/guides/events-meet).

### Meet Media API

A página de início informa Developer Preview e exige projeto Cloud, principal OAuth e todos os participantes inscritos. Também descreve escopos restritos e restrições de plataforma/idade. Revalidar essas condições antes de qualquer piloto. [Requisitos da Meet Media API](https://developers.google.com/workspace/meet/media-api/guides/get-started).

Não presumir que uma track representa sempre a mesma pessoa: o Google descreve streams virtuais e identificação da origem por CSRC. Há controles de consentimento e participantes podem interromper o acesso. Implementar resolução de fonte ao longo do tempo, não um dicionário fixo track→nome. [Visão geral e CSRC](https://developers.google.com/workspace/meet/media-api/guides/overview).

### Transporte da extensão

Recomendação inicial: content script coleta somente dados permitidos e manda mensagens ao service worker; este valida `sender`, origem, aba e sessão, e mantém a conexão autenticada com o aplicativo. WebSockets em service workers são documentados pelo Chrome; comunicação periódica e ciclo de suspensão/reconexão precisam de teste. [WebSockets em service workers](https://developer.chrome.com/docs/extensions/how-to/web-platform/websockets).

Alternativa de endurecimento: Native Messaging elimina o listener WebSocket desse caminho e registra um host local com extensões autorizadas. Tem custo de instalador/registro no Windows e não é acessível diretamente pelo content script; usa-se service worker como intermediário. O host não pode ser um executor genérico de comandos. [Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging).

A documentação de rede do Chrome informa que content scripts fazem requisições em nome da origem da página. Isso reforça a necessidade de testar o handshake atual; não estabelece, sozinho, qual `Origin` foi emitido em cada versão do Chrome/Edge para o WebSocket desta extensão. [Requisições de extensões](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests).

## Decisão recomendada

**Base local:** corrigir o transporte, coletar roster e evidências de legenda, persistir eventos cifrados por sessão, transcrever loopback e mic, alinhar relógios e aplicar atribuição conservadora. O arquivo final pode mostrar `Ana Silva` quando houver evidência; caso contrário, `FALANTE_02 — identificação pendente`. Correções são persistidas por reunião e podem ser desfeitas.

**Complemento oficial:** conector OAuth desligado por padrão, com diagnóstico de capacidade da conta. Se houver entries acessíveis, usá-las como fonte oficial identificada; se houver apenas participantes, enriquecer o roster sem inferir autoria. Tratar homônimos, convidados, telefone, reentrada e falta de permissão.

**Experimental:** Media API somente com elegibilidade confirmada, ambiente de teste e aceite dos participantes. Não há contratação de serviço externo nem upload de áudio propostos para o núcleo local.

Extensão/legendas dependem do Meet online. “Local” aqui significa que o Transkriptor não envia áudio/transcrição a outro serviço de inferência; não significa que a reunião Google ocorre offline.
