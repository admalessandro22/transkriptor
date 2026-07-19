# Concept — Transkriptor 1.1

## Visão

Transkriptor é um assistente de reuniões que roda localmente no PC do usuário.
Ele detecta automaticamente Google Meets, transcreve o áudio em segundo plano,
separa os falantes e oferece um assistente de IA (via Ollama) para analisar
tudo que foi dito — sem enviar dados para a nuvem, sem custo recorrente.

## Problema

Reuniões geram decisões importantes que se perdem. Existem ferramentas
comerciais (Otter, Fireflies, tl;dv), mas elas:
- Eniam áudio/transcrição para servidores de terceiros
- Cobram assinatura mensal
- Não integram com LLMs locais para análise sob demanda

O usuário quer privacidade total, custo zero e uma ferramenta que funcione
"sozinha" — detecte a reunião, transcreva e esteja pronta para analisar.

## Solução

Um app de bandeja (system tray) para Windows que combina:

1. **Captura de áudio** — loopback WASAPI do alto-falante (som da reunião)
2. **Transcrição** — faster-whisper (offline, CPU)
3. **Diarização** — speechbrain (embeddings de voz) + clustering (pós-processamento)
4. **Assistente de IA** — página web local conversando com Ollama
5. **Detecção automática** — monitora janelas do navegador e inicia/para sozinho

## Personas

### Ana, a profissional ocupada
Faz 3-5 reuniões por dia. Quer que a transcrição aconteça sem ela pensar.
Ao final do dia, abre o assistente e pede "resuma as três reuniões de hoje".
Não tem paciência para configurar nada — quer instalar e esquecer.

### Carlos, o preocupado com privacidade
Trabalha com dados sensíveis. Não pode usar ferramentas em nuvem.
Precisa que tudo rode localmente e que possa auditar que nada sai do PC.

## Princípios de Design

1. **Invisível por padrão** — o app vive na bandeja; o usuário não precisa
   interagir para que funcione. Notificações aparecem quando algo importante
   acontece (início/fim de transcrição, erro crítico).

2. **Confiança por feedback** — sempre que o app faz algo (começa a gravar,
   para, salva), o usuário sabe. Nunca há "silêncio operacional" onde o
   usuário não tem certeza se está funcionando.

3. **Local e gratuito** — zero dependência de nuvem para a parte central
   (transcrição + diarização). O Ollama é local. A única dependência externa
   é o download inicial dos modelos.

4. **Recuperação automática** — o app nunca deve travar silenciosamente.
   Se uma thread morrer, um mecanismo de watchdog reinicia. Se a captura
   de áudio falhar, o usuário é notificado e o app tenta novamente.

5. **Progressão de complexidade** — o fluxo padrão é zero-configuração
   (detectar → transcrever → diarizar). Usuários avançados podem ajustar
   modelo, idioma, dispositivo de áudio via menu da bandeja.

## Diferenciais vs. Versão 1.0

A versão 1.0 funcionava como protótipo mas tinha problemas estruturais:

| Aspecto | 1.0 (atual) | 1.1 (meta) |
|---|---|---|
| Detecção de Meet | Falso-positivos, sem debounce | Confirmação por N ciclos, título específico |
| Memória | Acumula áudio em RAM (vazamento) | Stream para wav temporário em disco |
| Recuperação | Sem watchdog — thread morta = app morto | Watchdog reinicia threads críticas |
| Diarização | Bloqueia thread do monitor | Roda em thread dedicada |
| Feedback | Sem notificações | Toasts do Windows no início/fim/erro |
| Conversa IA | Sem contexto (cada pergunta isolada) | Histórico de mensagens enviado ao modelo |
| Acessibilidade | Selects customizados, sem ARIA | Foco visível, ARIA, contraste AA, teclado |
| Startup | Não inicia com o Windows | Entrada no shell:startup |
| Código | CLI duplica lógica do core | CLI é wrapper fino sobre Transcritor |

## Escopo da Versão 1.1

### Dentro do escopo
- Correção dos 12 bugs de engenharia identificados
- Correção dos 6 problemas UX identificados
- Notificações nativas do Windows
- Watchdog de threads
- Histórico de conversa no assistente
- Melhorias de acessibilidade
- Inicialização automática com o Windows

### Fora do escopo
- Suporte a outras plataformas (macOS/Linux)
- Captura de microfone do usuário (além do loopback)
- Gravação de vídeo
- Integração com calendário
- Multi-idioma na interface (mantém pt-BR)
- Sincronização em nuvem ou backup
- Versão móvel

## Métricas de Sucesso

- Reunião de 1h não ultrapassa 150 MB de RAM (meta: <100 MB)
- Detecção de Meet tem 0 falsos-positivos em uso normal
- App sobrevive a 24h de execução contínua sem travar
- Diarização não bloqueia detecção de novas reuniões
- Usuário novo consegue usar sem ler documentação
