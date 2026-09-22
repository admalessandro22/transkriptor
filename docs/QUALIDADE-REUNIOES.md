# Protocolo de qualidade de reuniões (T-13.G3)

Corpus mínimo (spec): 12 sessões consentidas, ≥180 minutos, ≥12 vozes,
≥300 turnos avaliáveis; ≥6 sessões reservadas para teste, separadas por
reunião e por falantes quando possível.

## Conjuntos

- **Calibração**: ajusta limiares (`IDENTIDADE_*`, `CALIBRACAO_IDENTIDADE_VERSAO`).
  Nunca avalia release.
- **Teste**: só métrica final. Sem sobreposição de reunião/falante com a
  calibração quando possível.

## Métricas (`scripts/avaliar_qualidade_reuniao.py`)

- **WER** por segmento (Levenshtein em tokens normalizados), média do corpus.
- **DER** temporal com política de sobreposição **declarada**
  (`perdoar`|`rigorosa`).
- **Precisão nominal seletiva** (meta ≥98%), **cobertura elegível** (meta ≥80%),
  cobertura total e **abstinências**, com **IC95% de Wilson**.
- Roster sem fala nunca conta como acerto; erro de eco ≤1% dos turnos.

## Rastreabilidade e privacidade

- Referências versionadas por **hash** (`ref_sha256` no relatório).
- **Nenhuma gravação pessoal é commitada**: só agregados e IDs sintéticos.
- Cada gate real exige autorização específica (DU-12); sem ela, PENDENTE.

## Portões físicos

- `python scripts/gate_reuniao_real.py --segundos 25` (captura+STT).
- `python scripts/gate_reuniao_real.py --segundos 600` (encerra F13.C).
- Gate de identificação G3 (Chrome e Edge, 3 pessoas, 2 abas, homônimos —
  roteiro em `plan.md`).
