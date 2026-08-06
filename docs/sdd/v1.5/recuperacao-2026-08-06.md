# Evidência de recuperação — 2026-08-06

Escopo de `T-10.G2`: separar as duas reuniões contidas na captura contínua,
produzir texto legível, registrar a lacuna conhecida e só então retirar os
artefatos indevidos da pasta ativa.

## Cadeia de custódia

- WAV combinado antes da extração: 759.552.044 bytes; SHA-256
  `ba80dad0881576aadc5ee2cc11a90c26f4e78105a87630346a705ee981524c59`.
- Reunião 1: 93.200.000 frames, 5.825 s, mono PCM16/16 kHz; SHA-256
  `ca41d6aa782f97029bf9201220284a07eb6851117e7dbb300ba1803787ab9e6b`.
- Reunião 2: 34.800.000 frames, 2.175 s, mono PCM16/16 kHz; SHA-256
  `5e3c60258000dca9fa91a177e86c43d41252ba068bf579ca6f341926c1e07dea`.
- O hash do combinado foi repetido depois das duas extrações e permaneceu
  idêntico.

## Resultados

| Reunião | Janela estimada | TXT | Segmentos | Observação |
|---|---|---|---:|---|
| 1 | 09:31:13–11:08:30 | `transcricao_2026-08-06_09h31_reuniao-1-recuperada.txt` | 815 | áudio recuperado de 5.825 s |
| 2 | 14:33:30–15:14:30 | `transcricao_2026-08-06_14h33_reuniao-2-recuperada.txt` | 136 | aviso de lacuna estimada de 285 s |

Cada resultado também possui versão `_diarizado.txt`. O modo automático tinha
produzido 653 e 88 rótulos, evidenciando clusters espúrios. A correção limita a
explosão automática, preserva a quantidade explícita e evita intervalos
visualmente nulos. Os dois arquivos foram regenerados com 12 grupos automáticos;
isso é separação acústica aproximada, não identificação nominal comprovada.

## Auditoria sem exposição do conteúdo

- TXT simples e diarizado: 815/815 e 136/136 segmentos, com conteúdo de cada
  segmento idêntico.
- Timestamps monotônicos, intervalos positivos e contidos na duração do WAV.
- UTF-8 sem caractere de substituição; proporção de segmentos únicos de 96,93%
  e 95,59%.
- Jobs `23d2b083377140e482ec89aa21774bfc` e
  `307c680d16104269a33be7f844ee9c2b`: estado `ready`, sem erro e com resultado
  existente.
- Nenhum trecho falado encontrado nos JSONs dos jobs nem em `transkriptor.log`.
- A validação automatizada prova integridade estrutural e preservação do texto;
  fidelidade palavra por palavra e identidade real dos falantes exigem escuta
  humana e não são declaradas como comprovadas.

## Retenção

Após a auditoria verde, estes arquivos saíram de `transcricoes/` e foram enviados
à Lixeira do Windows: o WAV combinado, o WAV paralelo do microfone e o `.tkpt`
ilegível. Os WAVs recortados, os quatro TXTs e os dois jobs permanecem. A Lixeira
é recuperável e continua usando espaço até ser esvaziada pelo usuário.
