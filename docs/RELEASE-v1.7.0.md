# Release v1.7.0 — Nomeia transcrições por título do Meet

**Data:** 2026-09-03 18:07 -03:00
**Tag:** `v1.7.0` @ `3ce3ef7` (master)
**Base:** `v1.6.0` + FR-12.A1

## Resumo

Cada transcrição agora herda o **nome da reunião do Google Meet** no文件名, no formato `transcricao_dd-mm-aa_HhM_<slug>.txt` (ex: `transcricao_03-09-26_16h39_Reuniao_Bolsistas_PROINOVE.txt`). Se o título for código (`abc-defg-hij`) ou “Meet - Google Chrome”, cai no antigo `transcricao_dd-mm-aa_HhM`.

Data também migrada de `yyyy-mm-dd` para **`dd-mm-aa`** conforme pedido.

## Mudanças

- `deteccao_reuniao.titulo_para_base:163` + `DetectorReuniao.titulo_reuniao_atual:278` — extrai `Meet: Nome` / `Meet – Nome`, descarta código, prioriza **extensão** (titulo limpo) > janela
- `meet_bridge._titulo_meet` + `content.js:50` heartbeat agora envia `document.title` (120c)
- `Transcritor:55` `titulo_reuniao` → `crypto_storage.nome_base_transcricao:264` (`%d-%m-%y_%Hh%M` + slug ≤40, sanitizado ASCII)
- `transcricao_core._abrir_arquivo:162` cabeçalho `Reuniao: <slug>`
- `fila_processamento.CHAVES_METADADOS` inclui `titulo_reuniao` + `app_processamento:168` persiste
- `crypto_storage._slug_para_base` + `caminho_transcricao_novo:275` aceita `titulo_reuniao`

## Exemplos

- `Meet: Reunião Bolsistas PROINOVE - Google Chrome` → `03-09-26_16h39_Reuniao_Bolsistas_PROINOVE`
- `Meet: Sprint Planning 123` → `Sprint_Planning_123`
- `Meet – abc-defg-hij` → `03-09-26_16h39` (sem slug)
- Header: `Reuniao: Reuniao_Bolsistas_PROINOVE`

## Testes

- `tests/test_titulo_reuniao_nome.py` 7 passed (extração, detector, Transcritor, base dd-mm-aa, prioridade extensão, header)
- `pytest -q` → **520 passed**
- Gate 25s + 600s com `v1.6.0` ainda válidos

## Commits

```
963171d feat: nomeia transcrições a partir do título do Meet (FR-12.A1)
17f6838 chore: bump versão para 1.7.0 com nomeação por título do Meet
3ce3ef7 fix: nome da transcrição usa data dd-mm-aa (ex: 03-09-26) + slug do Meet
```
