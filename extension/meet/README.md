# Transkriptor Meet Bridge — Instalação

Extensão **opcional** do Google Chrome que envia nomes dos participantes do Meet para o Transkriptor no seu PC. Com isso, a diarização pode usar nomes reais em vez de `FALANTE_01`, `FALANTE_02`, etc.

## O que a extensão faz (e o que não faz)

| Comportamento | Detalhe |
|---------------|---------|
| Entra na reunião como bot? | **Não** — nenhum participante extra aparece na call |
| Mostra botão ou painel no Meet? | **Não** — é silenciosa na interface da reunião |
| Onde aparece? | Só em `chrome://extensions`, como **Transkriptor Meet Bridge** |
| Como funciona? | `rtc.js` lê legendas e nomes direto da conexão do Meet (sem CC na tela); `parser.js` lê o DOM como reserva; `background.js` envia ao app via `ws://127.0.0.1:5051` |
| Precisa ligar legendas (CC)? | **Não** — a extensão recebe as legendas por um canal próprio, invisível na reunião |

A transcrição automática funciona **sem** a extensão. Instale-a apenas se quiser **nomes do Meet** na transcrição diarizada.

---

## Instalação simples (v2.0)

1. Instale o Transkriptor pelo `TranskriptorSetup.exe`: ele registra o **pareamento automático** (host `com.transkriptor.ponte`).
2. Adicione a extensão pela loja (**Adicionar ao Chrome/Edge**, nos primeiros passos da Central, quando a extensão estiver publicada).
3. Pronto: com o Transkriptor aberto, a extensão se conecta sozinha. Sem código para copiar.

As seções abaixo (carregar a pasta em modo desenvolvedor e parear à mão) continuam valendo **para desenvolvimento** ou se o host de pareamento não estiver registrado (`python -m instalador.registrar_host`). O ID fixo da extensão de desenvolvimento é `mkcfobdlgdaeplnklpfcioojjgjjoojo`. O pacote da loja sai de `python scripts/empacotar_extensao.py` (ver `LOJA.md`).

## Pré-requisitos

- **Windows** com o Transkriptor rodando (ícone na bandeja)
- **Google Chrome** ou **Microsoft Edge** (Chromium)
- Reunião aberta em `https://meet.google.com/...` **nesse navegador**

---

## Instalação passo a passo

### 1. Inicie o Transkriptor e pareie a extensão

Abra o app (`transkriptor.pyw`). Ele gera um código de pareamento de uso
único (Diagnóstico). **Não há mais segredo em `config.js`.**

1. Abra a página `pairing.html` da extensão (ou `chrome://extensions` → detalhes → página de pareamento)
2. No Transkriptor, abra **Diagnóstico** e copie o **código de pareamento** (começa com `pair-`)
3. Cole o código no campo e clique em **Parear** (ou Enter)
4. O service worker (`background.js`) guarda a credencial em `chrome.storage.local` e conecta. O pareamento **persiste**: vale 90 dias e se renova a cada uso, sobrevive a reinícios do Chrome e do app (o app guarda só um hash da credencial). Só é preciso parear de novo se a extensão for removida/recarregada sem a credencial ou após 90 dias sem uso

A página mostra o estado do pareamento com ícone e cor:

| Estado | O que significa | O que fazer |
|--------|-----------------|-------------|
| Carregando (anel girando) | código guardado; conectando ao app | aguarde; se não mudar, confira se **Identificar nomes do Meet** está ligado |
| Sucesso (✓ verde) | pareado e conectado; campo e botão ficam travados | pode fechar a página |
| Erro (! vermelho) | código inválido/incompleto ou service worker parado | siga o "Próximo passo" indicado na própria mensagem |

O visual vem de `pairing.css`, gerado por `python scripts/gerar_tokens.py --write`
a partir dos mesmos tokens da Central (a extensão não carrega nada do app nem
da rede; só o WebSocket local).

### 2. Ative a ponte no menu da bandeja

Clique com o botão direito no ícone do Transkriptor → **Identificar nomes do Meet** (deve aparecer ✓).

Isso liga o servidor local em `127.0.0.1:5051`.

### 3. Carregue a extensão no Chrome

1. Abra `chrome://extensions` (cole na barra de endereço)
2. Ative **Modo do desenvolvedor** (canto superior direito)
3. Clique em **Carregar sem compactação**
4. Selecione **esta pasta** (`extension/meet/`), não a pasta `extension/` pai

A extensão deve aparecer como **Transkriptor Meet Bridge**, versão igual à de `manifest.json`.

**Atalho pelo app:** menu da bandeja → **Instalar extensão Meet (pasta)** abre esta pasta no Explorer.

### 4. Entre no Meet

Abra ou atualize a aba do Google Meet no **mesmo navegador** onde a extensão está instalada.

### 5. Legendas sem CC (automático)

Não é preciso ligar as legendas no Meet. Ao entrar na chamada, `rtc.js` abre um
canal de legendas próprio na conexão do Meet (como fazem extensões de
transcrição): o servidor manda nome do dispositivo + texto por ele, e nada
aparece na tela nem para os outros participantes. Os nomes vêm do canal
`collections` e, na falta, do tile do participante.

- O texto da legenda chega no **idioma de legendas configurado no Meet**; a
  extensão não altera essa configuração. Para o Transkriptor o que importa é
  quem falou e quando — o texto final vem do Whisper.
- Se o canal não entregar nada, a extensão volta a ler a faixa de legendas do
  DOM (aí sim o CC precisa estar ligado).
- Outra extensão de transcrição (ex.: Tactiq) também abre um canal de legendas
  na mesma conexão. Com as duas ativas, o botão CC do Meet pode aparecer como
  "temporariamente indisponível"; se os nomes não chegarem, desative a outra.

---

## Verificar se está funcionando

1. Transkriptor com **Identificar nomes do Meet** ativo
2. Extensão habilitada em `chrome://extensions`
3. Meet aberto no Chrome (legendas CC não são necessárias)
4. Inicie uma transcrição (automática ou manual) com **Separar vozes** ativo
5. Ao salvar a diarização, os rótulos devem preferir nomes do Meet quando houver correlação temporal

Se o modo legendas estiver ativo mas nada for recebido, o Transkriptor pode mostrar: *"Ative legendas no Meet para identificar participantes"*.

---

## Prioridade dos rótulos na diarização

```
Nome do Meet  >  Nome cadastrado (vozes conhecidas)  >  VOCÊ  >  FALANTE_XX
```

---

## Solução de problemas

### Extensão instalada antes do Transkriptor

A credencial pode estar ausente ou expirada.

1. Abra o Transkriptor e gere um novo código de pareamento
2. Abra `pairing.html` e pareie novamente
3. Em `chrome://extensions`, clique em **Recarregar** na extensão
4. Atualize a aba do Meet (F5)

### Nomes não aparecem na transcrição

- A opção **Identificar nomes do Meet** está marcada na bandeja?
- A reunião está no **Chrome** (não só no app Meet nem em outro navegador sem extensão)?
- Recarregou a aba do Meet (F5) depois de instalar/atualizar a extensão? `rtc.js` só entra no carregamento da página.
- Há outra extensão de transcrição (Tactiq etc.) ativa? Teste com ela desligada.
- **Separar vozes** está ligado durante a gravação?

### WebSocket não conecta

- Confirme que o Transkriptor está rodando
- Firewall não deve bloquear `127.0.0.1:5051` (tráfego local)
- Reinicie o Transkriptor e recarregue a extensão

### Atualizou o projeto / copiou pasta nova

Repita o passo **Carregar sem compactação** ou use **Recarregar** em `chrome://extensions` após abrir o Transkriptor uma vez.

## Parser versionado (D3)

`parser.js` (v1) separa **roster** (tiles, sem alegar fala) de **legendas**
(nome+texto com id/revisão) e de **atividade** (sinal auxiliar). Tile visível
não prova fala; homônimos mantêm ids distintos; sem seletores conhecidos, a
capacidade é reportada como indisponível. Fixtures anonimizadas versionadas em
`tests/js/fixtures/meet-*-v1.html`; suíte em `tests/js/meet-parser.test.js`.

---

## Edge (Chromium)

No Edge: `edge://extensions` → **Modo de desenvolvedor** → **Carregar extensão descompactada** → selecione esta pasta.

---

## Privacidade

- A extensão só age em `https://meet.google.com/*`
- Dados vão apenas para o Transkriptor no seu PC (`127.0.0.1`)
- Nada é enviado para servidores externos pela extensão

Documentação completa do app: `docs/MANUAL-USUARIO.md` (seção 6).