# Handoff — o que falta depois da v1.9 (24/09/2026)

Para a próxima IA (ou pessoa) que assumir. Leia `AGENTS.md` primeiro; depois este arquivo.

## Estado atual

- Branch em uso: `remediacao-auditoria-v18` no checkout `C:\Projetos\transkriptor`. Contém a remediação v1.8 **e** a interface v1.9 (merge `71798b9`), versão `1.9.0` (`d34efd5`, `39be4ba`) e o código de pareamento na Central (`c05570b`).
- `master` não recebeu nada disso. Nenhum push, tag ou release foi feito.
- Worktree `.worktrees/sdd-v1.9-design` (branch `sdd-v1.9-design`) ficou como histórico; pode ser removido com `git worktree remove` depois do merge para `master`.
- App da bandeja rodando o código novo a partir do checkout principal (`pythonw transkriptor.pyw`). Configuração do usuário já com `usar_nomes_meet` e `modo_legendas_meet` ligados.
- Evidências completas: `docs/sdd/v1.9/evidencias/GATE-FINAL.md` (comandos, números, pendências).

## Pendências, em ordem

### 1. Parear a extensão do Meet no Chrome (só interativo)
A extensão **não está instalada** no perfil do Chrome. Passos:
1. `chrome://extensions` → Modo do desenvolvedor → Carregar sem compactação → `C:\Projetos\transkriptor\extension\meet`.
2. Bandeja → Abrir Transkriptor → Diagnóstico → **Gerar código de pareamento** → Copiar.
3. Abrir `pairing.html` da extensão (Detalhes → Opções da extensão), colar, **Parear** → "Pareado e conectado".
4. Ativar legendas (CC) no Meet.
Verificar: `transkriptor.log` mostra a sessão da extensão; em reunião, nomes aparecem em Participantes.

### 2. Decisão de segurança: persistir a credencial da extensão
Hoje (`meet_pareamento.Pareador`): convite vale 5 min (`MEET_CONVITE_SEG`), sessão vale 12 h (`MEET_SESSAO_SEG`) e só existe em memória; a extensão guarda em `chrome.storage.session`. Consequência: a cada reinício do app ou do Chrome é preciso parear de novo. O usuário quer nomes automáticos "em todas as reuniões". Opções a propor e só implementar com o ok dele:
- (a) persistir as sessões do `Pareador` (ex.: em `config_user.json`, como já se faz com `meet_bridge_token`) e usar `chrome.storage.local` na extensão; alongar `MEET_SESSAO_SEG` (ex.: 30 dias);
- (b) manter como está e documentar o re-pareamento.
Testes afetados: `tests/test_meet_bridge_seguranca.py`, `tests/js/background-pairing.test.js`, `tests/e2e/meet-transport.spec.js`.

### 3. Rodar a suíte no checkout principal com o app parado ou ocioso
A última rodada no checkout principal deu `913 passed, 104 errors`; os erros são do guarda do `conftest` ("teste alterou estado local real do usuário") porque o app estava **gravando** em `transcricoes/` durante os testes. No worktree isolado a mesma suíte deu `913 passed`. Repetir com o app ocioso:
```bash
python -m pytest tests/ -q --tb=short
npm run test:unit
npm run test:e2e
```

### 4. Validações ao vivo (item 5 do usuário)
- Roteiro do Narrador: `docs/sdd/v1.9/evidencias/roteiro-narrador.md`, preencher a coluna Resultado com data.
- Capturas na bandeja real: ícone em 100/150/200 % e menu aberto (`T-14.E1`, `T-14.E2`).
- Consentimento com o Windows de fato em 150/200 % (`T-14.E3`).
- Gates físicos da remediação v1.8 que continuam sem PASS (ver `docs/superpowers/plans/2026-09-22-remediacao-auditoria-v18.md`): captura 25/600 s, reunião consentida de três pessoas, instalação CUDA limpa, segunda partida real.

### 5. Release
Quando o usuário autorizar: merge de `remediacao-auditoria-v18` em `master`, `python scripts/gate_instalacao.py`, tag `v1.9.0`, `docs/RELEASE-v1.9.0.md` no modelo de `docs/RELEASE-v1.7.0.md`. Nada disso está autorizado ainda.

### 6. Ambiente (fora do projeto)
`python -m pip check` acusa `pdfplumber 0.11.10` sem `pdfminer-six` e com Pillow abaixo de 12.2 no Python global do usuário; não está em `requirements/`. Não mexer sem pedir.

## Regras que não podem regredir (resumo)
- Consentimento fail-closed: só "Gravar esta reunião" inicia captura (`tests/test_aviso_gravacao.py`, `test_portao_consentimento.py`).
- Nada que dispare callback sob `self._lock`; suíte nunca importa `transkriptor` nem escreve em `transkriptor.log`.
- Toda thread com `soundcard` dentro de `com_audio.com_inicializada()`.
- Flask sempre `127.0.0.1`; CSP normativa em `assistente_cabecalhos.py`; zero requisição externa (`tests/test_orcamento_front.py`, `tests/e2e/csp.spec.js`).
- `design/tokens.json` é a única fonte de cor; após mexer em CSS: `python scripts/gerar_tokens.py --check`.
- `config.VERSAO` é a única versão; extensão sincronizada por `scripts/sincronizar_versao_extensao.py --check`.
- Não reiniciar o app da bandeja sem conferir no log que não há reunião/gravação em andamento (`Monitor vivo: ... gravando=False`).
