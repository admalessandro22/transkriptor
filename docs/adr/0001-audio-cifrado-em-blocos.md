# ADR 0001 — Áudio cifrado em blocos (TKAS/1 adiado para E1)

- Estado: proposto (decisão e implementação em T-13.E1, após revisão de segurança)
- Data: 2026-09-19
- Contexto (T-13.C3): leitura de áudio longo precisa de streaming em blocos
  ≤30 s com PCM 16/24/32 explícito; o `.wav.enc` legado é AES-GCM monolítico
  (decifragem integral em memória) com limite declarado em
  `config.AUDIO_CIFRADO_LEGADO_MAX_BYTES` (256 MiB).

## Requisitos do formato em blocos

1. Escrita/leitura sequencial com pico de RAM independente da duração.
2. Detecção de truncamento, reordenação, duplicação e alteração de chunks.
3. Chave derivada (nunca persistida) e validação antes de qualquer `unlink`.
4. Leitura parcial sem decifrar o arquivo inteiro.

## Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| TKAS/1 sobre PyNaCl SecretStream (`interfaces.md`) | Detecção de todas as falhas acima; primitiva auditada | Exige PyNaCl/libsodium na matriz Windows; estudos de chunk/AD |
| AES-GCM por chunk com índice | Reusa `crypto_storage`; simples | Reordenação/duplicação exigem índice autenticado à parte |
| Manter `.wav.enc` monolítico | Zero mudança | Pico de RAM proporcional ao áudio; sem leitura parcial |

## Decisão

C3 **não implementa container novo**: mantém o legado com limite explícito e
documenta requisitos/riscos aqui. TKAS/1 será decidido e implementado em E1.

## Riscos

- Áudio >256 MiB em modo protegido fica sem rota até E1 (erro explícito, sem
  fallback silencioso).
- Falha de autenticação descarta o parcial e preserva a fonte (política de E1).
