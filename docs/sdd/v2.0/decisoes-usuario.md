# Decisões do usuário — SDD v2.0

Estado em 29/09/2026: **todas respondidas pelo usuário** (tabela "Respostas"). A tabela "Decisões pendentes" preserva a pergunta, a recomendação e o padrão originais para auditoria.

## Pedido original (registro)

> 29/09/2026: descobrir como a Tactiq retira os dados para organizar as reuniões e inserir o nome dos participantes e o horário de fala; copiar essa funcionalidade; identificar o que mais ela faz para a transcrição ficar exata com o nome de cada pessoa, como no Google Meet; diagnóstico completo e plano SDD. Permitir escolher, nas configurações, qual IA local transcreve e qual resume, ou usar chave de API do OpenRouter. O instalador deve detectar se o Ollama já está instalado e trazer os modelos para o seletor, ou aceitar chave de API, e a instalação deve ser tão simples quanto a da Tactiq.

Leitura: "copiar a funcionalidade" = reimplementar a técnica e o comportamento com código próprio. O código da Tactiq é proprietário e não será reproduzido.

## Respostas (29/09/2026)

| ID | Resposta | Consequência no plano |
|---|---|---|
| DP-15-01 | **Sim, seguir transcrição** | `meet_idioma_legenda` padrão `seguir_transcricao`; T-15.B1 liberada |
| DP-15-02 | **Sim, desde já** (divergiu da recomendação) | Nome automático com limiares provisórios em `config.py` assim que C2/C3 estiverem prontos; T-15.F1 recalibra. A origem e a confiança ficam visíveis, e a correção manual prevalece. Não depende mais do corpus para ser ativado |
| DP-15-03 | **Opção ligada por padrão** (divergiu da recomendação) | `meet_capturar_chat` padrão `true`; desligar interrompe a decodificação e a persistência de chat |
| DP-15-04 | **Sim, opt-in por função** | Emenda DU-02: o texto da transcrição pode ir ao OpenRouter somente para a função escolhida (resumo e/ou chat), após consentimento datado; áudio, voz e biometria nunca saem |
| DP-15-05 | **Loja, não listada** (Chrome Web Store + Edge Add-ons) | O ID vem do item da loja; a publicação é feita pelo usuário |
| DP-15-06 | **Inno Setup + `uv`** | Conforme T-15.E4 |
| DP-15-07 | **Não assinar agora** | O manual explica o aviso do SmartScreen; a assinatura volta à pauta quando houver distribuição a terceiros |
| DP-15-08 | **2.0.0 ao fechar** | Bump apenas após o gate T-15.F1 |
| DP-15-09 | **Somente Ollama local** | URL restrita a loopback |
| DP-15-10 | **Sim, se executado inteiro** | T-15.F1 fecha também v1.8 D2/G3 no que se refere a nomes e instalação |
| DP-15-11 | **Modelo sugerido pelo hardware** | Sem modelo no Ollama: leve (~2 GB) sem GPU ou com RAM < 16 GB; maior (~9 GB) com GPU ≥ 8 GB de VRAM ou RAM ≥ 32 GB. Os nomes finais são conferidos na biblioteca do Ollama na implementação |
| DP-15-12 | **Ordem: lote de precisão primeiro** | A1 → A2 → C1 → C2 → B1 → B2 → demais da Trilha 1; depois D1–D3 e E1–E5 |

## Autorizações concedidas (29/09/2026)

- Registrar as decisões e implementar a v2.0 task a task, com TDD e commit local por task, na branch `sdd-v2.0-nomes-ia-instalador`, começando por T-15.A1.
- Continuam **não** autorizados: push, publicação, bump, reunião real, extensão em perfil real, chave OpenRouter real e setup fora de sandbox.

## Decisões pendentes

| ID | Pergunta | Recomendação | Padrão sem resposta | Bloqueia |
|---|---|---|---|---|
| DP-15-01 | A extensão pode **alterar o idioma da legenda** da sua sessão no Meet para o idioma da transcrição, como a Tactiq faz? Isso só muda as legendas que você recebe e nada muda para os outros participantes. | **Sim**, com `seguir_transcricao` como padrão. É a maior causa isolada de legenda inútil. | `nao_alterar` (só lê o idioma e avisa) | T-15.B1 |
| DP-15-02 | Aplicar nomes **automaticamente** quando a confiança calibrada for alta, sem clicar em "Confirmar"? | **Sim**, depois da calibração em T-15.F1. Até lá, automático só em reunião de teste. | Sugestão (comportamento atual) | T-15.C3 |
| DP-15-03 | Capturar o **chat** do Meet na transcrição? | Opção disponível e **desligada por padrão**. | Desligado e sem código ativo | T-15.B5 |
| DP-15-04 | Permitir **OpenRouter** para resumo e chat, emendando DU-02 ("processamento local")? Envia o texto da transcrição e as perguntas; nunca áudio nem voz. | **Sim, como opt-in** por função, com consentimento datado e marca em cada saída. Transcrição continua sempre local. | Não; somente Ollama | T-15.D2 (e a opção em D3/E3) |
| DP-15-05 | **Publicar a extensão** na Chrome Web Store (não listada) e no Edge Add-ons? Exige conta de desenvolvedor (taxa única do Google), política de privacidade pública e revisão. A publicação é feita por você. | **Sim, não listada.** É o que dá o "um clique" e o ID fixo. | Chave de desenvolvimento local; modo desenvolvedor continua | T-15.E1 (origem do ID), T-15.E5 |
| DP-15-06 | Formato do instalador | **Inno Setup + `uv` embutido**, que provisiona o runtime a partir dos lockfiles com hash durante a instalação: setup pequeno, rota CPU/CUDA e reuso do gate atual. A alternativa PyInstaller gera 2–4 GB com torch/CUDA e costuma quebrar SpeechBrain/ctranslate2. | Inno Setup + `uv` | T-15.E4 |
| DP-15-07 | **Assinar o setup** com certificado de código? Sem assinatura, o SmartScreen avisa na primeira execução. | Sim, se houver distribuição para terceiros. Para uso próprio e da equipe, pode ficar para depois. | Sem assinatura, com instrução no manual | T-15.E4 (aceite) |
| DP-15-08 | Versão do produto ao fechar a v2.0 | `2.0.0` (instalador novo + protocolo de envelope v2) | Sem bump | T-15.F1 |
| DP-15-09 | Permitir Ollama em **outra máquina da rede** (URL não loopback)? | Não nesta versão. | Somente loopback | T-15.D1 |
| DP-15-10 | T-15.F1 pode substituir os gates físicos pendentes da v1.8 (D2/G3) relativos a nomes e instalação? | Sim, se executado integralmente com 3 reuniões consentidas. | Não; os gates v1.8 continuam abertos | T-15.F1 |

## Autorizações necessárias (separadas das decisões)

- Implementar a v2.0: commits locais task a task.
- Reunião de teste real (captura, idioma, próprio dispositivo) e consentimento dos participantes para o corpus.
- Instalar a extensão num perfil de teste do Chrome/Edge e registrar o host nativo nesse perfil.
- Usar uma chave OpenRouter de teste, com limite de gasto definido por você.
- Rodar o setup em Windows Sandbox/VM.
- Push, PR, publicação na loja e release.

## Condição para nova consulta

Voltar ao usuário antes de prosseguir se:

- o protocolo observado divergir do descrito no diagnóstico;
- a loja exigir mudança de permissão;
- o OpenRouter mudar a política de retenção;
- `word_timestamps` custar mais de 15% em CPU;
- qualquer meta do concept não puder ser atingida.
