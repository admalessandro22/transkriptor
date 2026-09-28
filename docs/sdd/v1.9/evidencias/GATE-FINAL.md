# Gate final — SDD v1.9 (F14.G)

Data: 24/09/2026 · Branch: `sdd-v1.9-design` · SHA base do gate: `25660ff`; commit de T-14.G1: `b36cc8f` · `config.VERSAO = 1.7.0` (sem bump, DP-14-11) · Ambiente: Windows 11 Pro 22000, Python 3.12.10, Node 22.22, Playwright 1.63 (Chromium), `@axe-core/playwright` 4.13, Pillow 12.1. Nenhum push, tag ou release. Branch `remediacao-auditoria-v18` intocada (`48b7173`).

## Comandos do gate G (`plan.md`) e resultados

| Comando | Resultado | Exit |
|---|---|---|
| `python -m pytest tests/ -q --tb=short` | **913 passed**, 8 warnings, 4 min 27 s | 0 |
| `python scripts/verificar_fase.py --fase all` | `RASTREABILIDADE OK` (v1.8, raiz padrão) + **236 passed** nas fases 0–8/estabilidade | 0 |
| `python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9` | `RASTREABILIDADE OK`; com `--tarefa T-14.G1` os seletores do teste final existem | 0 |
| `npm ci` | reinstalação a partir do lock, 0 vulnerabilidades | 0 |
| `npm run test:unit` | **34 passed** (6 arquivos) | 0 |
| `npm run test:e2e` | **150 passed**, 1,6 min | 0 |
| `python -m pip check` | 2 avisos pré-existentes do ambiente, fora do projeto: `pdfplumber 0.11.10` pede `pdfminer-six` e `Pillow>=12.2.0` (pacote não listado em `requirements/`; ver "Observações") | 1 |
| `git diff --check` | sem espaço sobrando | 0 |

Complementares: `python scripts/gerar_tokens.py --check` → `TOKENS OK`; `python scripts/gerar_icones.py --check` → `ICONES OK` (via `tests/test_icones.py`); `detect.mjs` → `[]` em todos os CSS/HTML tocados; `node docs/sdd/v1.9/evidencias/T-14.F2/medir_render_servidor.js` → pior FCP morno 108 ms.

## Fases e tasks

| Fase | Tasks | Commits (feat/test + docs) | Gate da fase |
|---|---|---|---|
| A | A1 `488e1da`, A2 `04baf8f`, A3 `d367631` | evidências `T-14.A1..A3.md` | verde (A3) |
| B | B1 `a93be9c`, B2 `87bcd9d`, B3 `6480053`, B4 `fb873e7` | `T-14.B1..B4.md` | verde (B4) |
| C | C1 `d55f11b`, C2 `93711da`, C3 `2041c5a` | `T-14.C1..C3.md` | verde (C3) |
| D | D1 `ad30422`, D2 `43dc10a`, D3 `79f8999`+`3ae03be` | `T-14.D1..D3.md` | verde (D3) |
| E | E1 `4f3ca57`, E2 `030b57d`, E3 `8064f2c`, E4 `3b2b8a9`, E5 `9e2418a` | `T-14.E1..E5.md` | verde (E5: 906 py / 87 e2e / 34 unit) |
| F | F1 `09b315e`, F2 `1fa6829` | `T-14.F1.md`, `T-14.F2.md`, `roteiro-narrador.md` | verde (F2: 909 py / 150 e2e / 34 unit) |
| G | G1 (este documento) | `T-14.G1.md` | verde (tabela acima) |

## Gate visual (plan.md) — revisão das capturas finais

1. Nenhum hex/tamanho/duração fora dos tokens: `test_sem_hex_fora_de_tokens_css`, `--check` do gerador; componentes só da galeria (revisão das 14 capturas de `T-14.G1/`).
2. Estados por componente na galeria: vazio, carregando, erro, sucesso, desabilitado, foco (`galeria.spec.js` + snapshots).
3. Glossário: nenhum `FALANTE_XX` cru nas páginas (Falante 1, 2…), nenhum ".tkpt"/"diarizado" como badge (Protegida/Legível, Separar vozes), erros com próximo passo (`estados.spec.js`, `pairing-ui.test.js`).
4. Tema claro e escuro, `forced-colors`, 375/900/1366/1920: `axe.spec.js`, `larguras.spec.js`.
5. Foco visível por Tab, Esc fecha e restaura: `accessibility.spec.js`, `shell.spec.js`, `exportar.spec.js`.
6. Nenhum dado real: fixtures de `tests/e2e/fixtures/central.js`; capturas nativas com dados fictícios e respondidas com Não/timeout.

## Capturas (manual e evidências)

- Manual: `docs/manual/capturas/` — 20 PNGs (ícone, consentimento 100/200 %, confirmação bandeja + Central dark/light, seis páginas da Central dark/light, pareamento dark/light); origem em `docs/manual/capturas/README.md`.
- Evidências: `T-14.A3` … `T-14.G1` (78 PNGs antes de G1 + 14 finais), `T-14.E2/menu-arvore.txt`, `T-14.F1/axe-relatorio.json` e `aria/*.yaml`, `T-14.F2` medições.

## Decisão de versão (DP-14-11)

Registrada em `decisoes-usuario.md`: nenhum bump nesta branch; recomendação `1.9.0` na release seguinte, com `scripts/sincronizar_versao_extensao.py` e `scripts/gate_instalacao.py`. A execução é do usuário.

## Pendências fora do alcance automatizado (não bloqueiam o gate, ficam listadas)

1. **Roteiro do Narrador ao vivo** (`roteiro-narrador.md`): a coluna "Resultado" exige sessão interativa com o Narrador do Windows; a execução automatizada (snapshots ARIA + specs) está registrada.
2. **Capturas na bandeja real** (ícone em 100/150/200 % de escala do Windows, menu aberto): exigem o app rodando na sessão do usuário; o ícone foi validado por composição (`T-14.E1`) e o menu pela árvore gerada com o pystray real (`T-14.E2`).
3. **Consentimento com o Windows de fato em 150/200 %**: as capturas forçam o DPI por parâmetro (`T-14.E3`).
4. **`pip check`**: os dois avisos vêm de `pdfplumber` instalado no ambiente global do desenvolvedor, fora de `requirements/`; não foi alterado nada de dependências Python (não autorizado).

## Observações

- `package.json`: `test:e2e` passou a chamar `node node_modules/@playwright/test/cli.js` porque o shim `playwright` do npm, no Windows, carregava o runner por um caminho com outra caixa (`C:\Projetos` × `C:\projetos`) e duplicava o módulo (`No tests found`). Mesmos testes, mesma configuração.
- Suíte Python: nunca escreve em `transkriptor.log` (fixture `log_de_teste`); nenhum teste importa `transkriptor`.
