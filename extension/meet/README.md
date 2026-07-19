# Transkriptor Meet Bridge — Instalação

Extensão **opcional** do Google Chrome que envia nomes dos participantes do Meet para o Transkriptor no seu PC. Com isso, a diarização pode usar nomes reais em vez de `FALANTE_01`, `FALANTE_02`, etc.

## O que a extensão faz (e o que não faz)

| Comportamento | Detalhe |
|---------------|---------|
| Entra na reunião como bot? | **Não** — nenhum participante extra aparece na call |
| Mostra botão ou painel no Meet? | **Não** — é silenciosa na interface da reunião |
| Onde aparece? | Só em `chrome://extensions`, como **Transkriptor Meet Bridge** |
| Como funciona? | Lê a página do Meet (tiles e legendas CC) e envia nomes para `ws://127.0.0.1:5051` |

A transcrição automática funciona **sem** a extensão. Instale-a apenas se quiser **nomes do Meet** na transcrição diarizada.

---

## Pré-requisitos

- **Windows** com o Transkriptor rodando (ícone na bandeja)
- **Google Chrome** ou **Microsoft Edge** (Chromium)
- Reunião aberta em `https://meet.google.com/...` **nesse navegador**
- Para melhor resultado: **legendas (CC) ativadas** no Meet

---

## Instalação passo a passo

### 1. Inicie o Transkriptor

Abra o app (`transkriptor.pyw`). Ele gera o token de segurança e grava em `config.js` desta pasta. **Não edite `config.js` manualmente.**

### 2. Ative a ponte no menu da bandeja

Clique com o botão direito no ícone do Transkriptor → **Identificar nomes do Meet** (deve aparecer ✓).

Isso liga o servidor local em `127.0.0.1:5051`.

### 3. Carregue a extensão no Chrome

1. Abra `chrome://extensions` (cole na barra de endereço)
2. Ative **Modo do desenvolvedor** (canto superior direito)
3. Clique em **Carregar sem compactação**
4. Selecione **esta pasta** (`extension/meet/`), não a pasta `extension/` pai

A extensão deve aparecer como **Transkriptor Meet Bridge**, versão 1.0.0.

**Atalho pelo app:** menu da bandeja → **Instalar extensão Meet (pasta)** abre esta pasta no Explorer.

### 4. Entre no Meet

Abra ou atualize a aba do Google Meet no **mesmo navegador** onde a extensão está instalada.

### 5. Modo legendas (recomendado)

1. No Meet, ative **Legendas** (ícone CC)
2. Na bandeja do Transkriptor: **Modo legendas Meet (Tactiq)** (✓)

A extensão lê o nome do falante nas legendas — método mais confiável que detectar só pelo tile de vídeo.

---

## Verificar se está funcionando

1. Transkriptor com **Identificar nomes do Meet** ativo
2. Extensão habilitada em `chrome://extensions`
3. Meet aberto no Chrome com legendas ligadas
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

O `config.js` pode estar com token inválido (`placeholder`).

1. Abra o Transkriptor (ele regrava o token)
2. Em `chrome://extensions`, clique em **Recarregar** na extensão
3. Atualize a aba do Meet (F5)

### Nomes não aparecem na transcrição

- A opção **Identificar nomes do Meet** está marcada na bandeja?
- A reunião está no **Chrome** (não só no app Meet nem em outro navegador sem extensão)?
- Legendas (CC) estão **ativas** no Meet?
- **Separar vozes** está ligado durante a gravação?

### WebSocket não conecta

- Confirme que o Transkriptor está rodando
- Firewall não deve bloquear `127.0.0.1:5051` (tráfego local)
- Reinicie o Transkriptor e recarregue a extensão

### Atualizou o projeto / copiou pasta nova

Repita o passo **Carregar sem compactação** ou use **Recarregar** em `chrome://extensions` após abrir o Transkriptor uma vez.

---

## Edge (Chromium)

No Edge: `edge://extensions` → **Modo de desenvolvedor** → **Carregar extensão descompactada** → selecione esta pasta.

---

## Privacidade

- A extensão só age em `https://meet.google.com/*`
- Dados vão apenas para o Transkriptor no seu PC (`127.0.0.1`)
- Nada é enviado para servidores externos pela extensão

Documentação completa do app: `docs/MANUAL-USUARIO.md` (seção 6).