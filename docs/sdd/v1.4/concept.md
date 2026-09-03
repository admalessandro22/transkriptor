# Concept — Transkriptor v1.4

## O problema relatado

> "Eu dou dois cliques e ele abre, vai para a bandeja do sistema. Porém ele não
> começa a fazer a gravação das reuniões, a transcrição."

O app subia, o ícone aparecia, o menu funcionava — e nenhuma reunião era gravada.
Nenhum erro na tela, nenhum erro no log.

## A auditoria

A investigação partiu das evidências da própria máquina do usuário, não de
suposições:

1. **`transkriptor.log`** — última execução em 2026-07-21 10:49 registrou
   "Bandeja pronta" e "Monitor do Meet iniciado", e depois **nada** por dois dias.
   O monitor só escrevia no log em mudança de estado; silêncio significava
   "nenhuma reunião foi vista".
2. **`transcricoes/audio/`** — todos os `.wav.enc` tinham **77 bytes**: um
   cabeçalho WAV vazio criptografado. Zero quadros de áudio. As gravações que
   chegaram a acontecer produziram arquivos vazios.
3. **Reprodução direta** — chamar `soundcard` fora do app levantou exceção na
   primeira leitura de áudio.

Conclusão: **duas falhas independentes**, ambas silenciosas, cada uma suficiente
para o sintoma.

## Causa raiz 1 — a captura de áudio estava quebrada

`soundcard 0.4.3` usa `numpy.fromstring`, removida no numpy 2.0. Com
`numpy 2.4.2` instalado, **toda** chamada de gravação levanta:

```
ValueError: The binary mode of fromstring is removed, use frombuffer instead
```

O `requirements.txt` pedia `soundcard==0.4.3` com `numpy>=1.24` sem teto — uma
instalação nova sempre caía nessa combinação.

O que tornou a falha invisível foi o laço de captura:

```python
try:
    data = rec.record(numframes=frames)
except Exception:
    time.sleep(0.5)
    continue        # <- erro engolido, para sempre, sem log
```

O app "gravava" indefinidamente sem capturar um único quadro.

## Causa raiz 2 — o detector não reconhecia mais o Google Meet

O regex exigia o formato **legado** `<sala> - Google Meet`. O Meet hoje intitula
a aba como `Meet – abc-defg-hij` (com travessão). Nenhum dos dois padrões
alternativos cobria isso, então o título real de uma reunião nunca casava.

Agravantes encontrados no mesmo caminho:

- **Só a aba em primeiro plano é visível.** `getAllTitles()` devolve o título da
  janela, que é o da aba ativa. Entrar na reunião e trocar de aba fazia o título
  sumir; em 15 s o detector concluía "reunião encerrada" e finalizava a gravação
  no meio da conversa.
- **A lista de exclusão derrubava reuniões legítimas.** "ajuda", "help" e
  "novidades" eram testadas mesmo contra um casamento inequívoco: uma sala
  chamada "Ajuda ao cliente" era descartada.
- **A fonte mais confiável estava desligada.** A extensão do Meet roda dentro da
  página e sabe com certeza se você está em chamada — mas só era usada para nomes
  de participantes, e apenas com "Identificar nomes do Meet" ligado.

## Achados secundários da auditoria

| # | Achado | Efeito |
|---|--------|--------|
| A1 | Limiar de VRAM em 4.0 GB exatos | A GTX 1650 reporta 3.99969 GiB e caía sempre para `small`/CPU — o oposto do que a spec v1.3 pedia |
| A2 | Lock de instância única por PID em arquivo | Encerramento forçado deixa o arquivo; o Windows recicla o PID; o app recusa iniciar para sempre ("já está em execução", sem ícone) |
| A3 | Início/fim da transcrição na thread do monitor | Carregar o Whisper bloqueia a detecção por dezenas de segundos, justo no começo da reunião |
| A4 | `_iniciar_transcricao` sem portão atômico | Monitor e menu manual podiam abrir duas capturas disputando o loopback |
| A5 | Ausência de qualquer autodiagnóstico | Duas falhas críticas ficaram dias invisíveis |

## A decisão de projeto

Trocar **uma** fonte de detecção por **três independentes**, combinadas por OR:

| Fonte | Força | O que resolve |
|-------|-------|---------------|
| Título da janela | forte | Caso comum; agora com o formato atual do Meet e com Zoom |
| Microfone em uso (registro do Windows) | fraca | Aba em segundo plano, janela minimizada, Zoom, Teams — sem regex nova |
| Ponte da extensão | forte | Certeza absoluta quando a extensão está instalada |

Regra de fusão, escolhida a partir do custo de cada erro:

- **Qualquer** fonte mantém a reunião viva → acaba o falso "encerrou" ao trocar
  de aba. Perder o fim custa alguns segundos de áudio a mais; cortar no meio
  custa a reunião inteira.
- Para **iniciar**, uma fonte forte basta em 2 ciclos (10 s); só o microfone
  exige 4 ciclos (20 s) → um `chrome.exe` que abriu o microfone para um áudio de
  WhatsApp não vira reunião.

A fonte do microfone lê o mesmo registro que acende o ícone de microfone da barra
de tarefas do Windows (`CapabilityAccessManager\ConsentStore\microphone`), e só
considera apps de conferência — senão ditado por voz (WisprFlow) viraria reunião.

## Fluxo pedido pelo usuário

> "Quando a reunião inicia, que ele me pergunte se eu quero gravar ou não."

Mantido o desenho **gravar primeiro, perguntar depois**: a captura começa no
instante da detecção e o diálogo Sim/Não aparece em seguida. Perguntar antes
custaria os primeiros 30 segundos de fala — normalmente a pauta da reunião. O
"Não" para e **apaga** o que foi gravado; o silêncio (30 s) mantém gravando.

Novidades v1.4: um toast precede o diálogo (o Windows pode abrir a MessageBox
atrás do navegador) e a pergunta virou opção de menu, para quem prefere gravar
sempre sem ser interrompido.

## Escopo fora desta versão

- Detecção de reunião por conteúdo de áudio (VAD de fala contínua).
- Suporte a Teams/Webex por título — hoje cobertos apenas pela fonte do microfone.
- Extensão publicada na Chrome Web Store (segue como carga descompactada).
