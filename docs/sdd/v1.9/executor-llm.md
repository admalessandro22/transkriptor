# Protocolo de execução para LLM — SDD v1.9 (design)

Normativo para qualquer LLM que implemente a v1.9. Ordem de precedência em conflito: instruções de sistema/usuário → `AGENTS.md` → `decisoes-usuario.md` (v1.9 e DU-* da v1.8) → `plan.md` → `concept.md` → `spec.md` → `design-system.md` → `interfaces.md` → `tasks.md` → este protocolo. Registrar o conflito e parar antes de alterar comportamento.

## 1. Escopo autorizado e não autorizado

Uma autorização para "executar o plano v1.9" permite alterar código, testes, estáticos, templates, ícones e documentação apenas da task corrente, rodar testes locais, gerar capturas sintéticas e criar o commit local previsto. Não permite, sem autorização separada:

- `push`, release, tag, bump de `config.VERSAO`, publicação da extensão;
- instalar dependência além de `@axe-core/playwright` (DP-14-09), ou qualquer dependência de runtime;
- carregar fonte, script, estilo, imagem ou ícone de origem externa; usar CDN;
- abrir transcrições, áudios, `config_user.json`, chaves ou logs reais; capturar tela com dados reais;
- alterar `transcricao_core.py`, `captura_leve.py`, `fila_processamento.py`, `processador_reuniao.py`, `crypto_*`, `politica_privacidade.py`, `identidade_reuniao.py`, `resultado_*.py`, `meet_bridge.py`;
- remover item de menu ou diálogo Tk antes da página equivalente da Central estar verde na mesma task;
- executar gate físico de áudio ou reunião real (a v1.9 não precisa de nenhum; se parecer necessário, parar e perguntar).

## 2. Leitura obrigatória e pré-checagem

```powershell
git status --short --branch
git rev-parse HEAD
python -c "import config; print(config.VERSAO)"
Get-Content AGENTS.md
Get-Content docs/sdd/v1.9/plan.md
Get-Content docs/sdd/v1.9/concept.md
Get-Content docs/sdd/v1.9/spec.md
Get-Content docs/sdd/v1.9/design-system.md
Get-Content docs/sdd/v1.9/interfaces.md
Get-Content docs/sdd/v1.9/tasks.md
Get-Content docs/sdd/v1.9/decisoes-usuario.md
python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9
```

Depois: identificar a primeira task `PENDING` cujas dependências estejam `DONE`; conferir `git log -10 --oneline`, `git diff --name-only`; não sobrescrever alteração local do usuário; rodar o baseline da task antes do RED (baseline vermelho é bloqueio, não RED).

## 3. Regras específicas de front-end

1. **Tokens primeiro.** Nenhum valor visual literal em CSS fora de `tokens.css`. Se um valor novo for necessário, adicionar ao JSON, regenerar (`--write`), e o teste de contraste decide.
2. **Sem inline.** Nenhum `style=`, `<style>` ou `<script>` inline no HTML. JS altera classes. Toda página é testada sob a CSP normativa.
3. **Testes legados.** Um teste de substring só pode ser removido quando um teste comportamental equivalente é adicionado na mesma task; a evidência lista "removido X → coberto por Y". Nunca reduzir cobertura de comportamento (cancelamento, isolamento por reunião, escape de HTML, foco restaurado, 409).
4. **IDs de contrato.** Manter os IDs de `interfaces.md` §3. Quando um controle muda de natureza, migrar os testes E2E na mesma task com o helper indicado.
5. **Dados sintéticos.** Capturas, galeria e E2E usam `tests/e2e/fixtures/`. Nenhum nome de pessoa real, nenhum caminho pessoal.
6. **Glossário.** Todo texto novo de interface usa `design-system.md` §9. `FALANTE_XX`, `.tkpt`, `cluster`, `diarizado` não aparecem ao usuário.
7. **Estados obrigatórios.** Toda lista tem vazio, carregando, erro e sucesso; todo botão assíncrono tem loading; toda ação irreversível tem consequência e botão padrão seguro.
8. **Movimento.** Durações e easing só pelos tokens; nada acima de 240 ms; nada infinito fora de progresso.
9. **Python.** Arquivos ≤ 500 linhas; nada sob `self._lock` que dispare callback; `app_estado_ui.snapshot` nunca pede lock nem lê conteúdo.
10. **Windows.** Consentimento e bandeja: preservar `pedir_consentimento`, timeouts, IDs de controle e testes de portão; novos recursos caem no comportamento atual em caso de falha.

## 4. Algoritmo fechado por task

1. Ler o bloco da task e os contratos citados.
2. Escrever os testes RED do bloco; rodar; confirmar falha pelo comportamento.
3. Implementar apenas os arquivos do bloco.
4. Migrar os testes legados listados; registrar o mapa remoção → cobertura.
5. Rodar `python scripts/gerar_tokens.py --check` se CSS mudou.
6. Rodar o teste final e a regressão; ambos verdes.
7. Gerar capturas (`node tests/e2e/capturar.js <task>`), revisar com o gate visual de `plan.md`, anexar à evidência.
8. Escrever `evidencias/T-14.Xn.md`: base SHA, comandos, exit codes, testes migrados, capturas, limitações.
9. Commit em português, imperativo, só os arquivos da task. Registrar o SHA na evidência e marcar a task `DONE` em `tasks.md`.
10. Se for a última task da fase, rodar o gate da fase e o gate visual antes de marcar a fase.

## 5. Condições de parada

Parar e reportar quando: um teste de comportamento legado só passa reduzindo cobertura; uma decisão DP-14-* precisa mudar; uma dependência nova é necessária; um arquivo Python ultrapassaria 500 linhas sem divisão natural; a CSP normativa quebra um recurso que não tem alternativa sem inline; uma captura só é possível com dados reais; qualquer conflito com trabalho local não commitado.

## 6. Formato de evidência

```markdown
# T-14.Xn — <título>
Base: <SHA antes> · Commit: <SHA depois> · Data: AAAA-MM-DD · Ambiente: Windows 11, Python X, Node Y
## Comandos e resultados
- `<comando>` → exit 0, N passed
## Testes migrados
- removido `arquivo::teste` → coberto por `arquivo::teste`
## Capturas (sintéticas)
- `capturas/T-14.Xn/<nome>.png` — o que mostra
## Gate visual
- [x] itens 1–6 do plano
## Limitações
```
