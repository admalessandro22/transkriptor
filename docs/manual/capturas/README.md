# Capturas do manual (SDD v1.9)

Todas as imagens são **sintéticas**: páginas reais da Central servidas com as
fixtures de `tests/e2e/fixtures/central.js` (reuniões e nomes inventados, como
"Ana Souza"), janelas nativas abertas com dados fictícios e respondidas com
"Não"/timeout. Nenhum arquivo de `transcricoes/`, `_modelo_voz/` ou
`config_user.json` foi lido. Regenerar: `node tests/e2e/capturar.js T-14.G1 <pagina> 1366`
e os scripts citados na coluna de origem.

| Arquivo | Superfície | Origem (evidência) |
|---|---|---|
| `bandeja-icones.png` | ícone da bandeja, seis estados, barra clara e escura | `docs/sdd/v1.9/evidencias/T-14.E1/` |
| `consentimento-100pct.png`, `consentimento-200pct.png` | janela de consentimento (Win32 real, DPI 96 e 192) | `T-14.E3/capturar_dialogo.py` |
| `confirmacao-bandeja.png` | MessageBox real da bandeja ("Pausar a gravação automática?") | `T-14.E4/capturar_bandeja.py` |
| `confirmacao-central-dark.png`, `confirmacao-central-light.png` | mesma confirmação na Central → Configurações | `T-14.E4/capturar_central.js` |
| `central-inicio-dark.png`, `central-inicio-light.png` | Central → Início | `tests/e2e/capturar.js T-14.G1 inicio` |
| `central-reunioes-dark.png`, `central-reunioes-light.png` | Central → Reuniões | `capturar.js T-14.G1 reunioes` |
| `central-assistente-dark.png`, `central-assistente-light.png` | Central → Assistente | `capturar.js T-14.G1 assistente` |
| `central-participantes-dark.png`, `central-participantes-light.png` | Central → Participantes | `capturar.js T-14.G1 participantes` |
| `central-configuracoes-dark.png`, `central-configuracoes-light.png` | Central → Configurações | `capturar.js T-14.G1 configuracoes` |
| `central-diagnostico-dark.png`, `central-diagnostico-light.png` | Central → Diagnóstico | `capturar.js T-14.G1 diagnostico` |
| `extensao-pareamento-dark.png`, `extensao-pareamento-light.png` | página de pareamento da extensão (estado sucesso) | `T-14.E5/capturar_pairing.js` |
