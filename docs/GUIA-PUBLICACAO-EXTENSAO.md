# Guia — publicar a extensão na Chrome Web Store e no Edge Add-ons

Tempo seu: ~40 min, mais a revisão das lojas (em geral de 1 a 3 dias úteis).

- **Pacote:** `dist\transkriptor-meet-2.0.0.zip`. Gere de novo com `python scripts/empacotar_extensao.py` sempre que a extensão mudar.
- **Textos prontos:** `extension/meet/LOJA.md`.
- **Política de privacidade:** `docs/PRIVACIDADE-EXTENSAO.md`.

## 0. Antes de começar

1. **Política de privacidade numa URL pública.** O jeito mais simples é um Gist público do GitHub, ou uma página no seu site, com o conteúdo de `docs/PRIVACIDADE-EXTENSAO.md`. Guarde a URL.
2. **Imagens da loja:**
   - Ícone 128×128: `extension/meet/icons/icone-128.png`.
   - Pelo menos 1 captura 1280×800: pode ser da página Primeiros passos ou do painel de participantes com dados fictícios. **Nunca** use uma reunião real.

## 1. Chrome Web Store

1. Acesse **https://chrome.google.com/webstore/devconsole** com a conta Google que vai publicar e pague a taxa única de registro de desenvolvedor.
2. **Novo item** → envie `dist\transkriptor-meet-2.0.0.zip`.
3. **Aba "Detalhes da página"**, copiando de `LOJA.md`:
   - nome, descrição curta e descrição completa;
   - categoria: Produtividade;
   - idioma: Português (Brasil);
   - ícone e captura.
4. **Aba "Privacidade":**
   - Finalidade única: copie de `LOJA.md` ("Uso único").
   - Justificativa de cada permissão (`storage`, `nativeMessaging`, acesso a `meet.google.com`): copie de `LOJA.md`.
   - Coleta de dados: marque que o conteúdo do site (legendas e nomes) é **lido**, mas **não é transferido** a terceiros nem vendido. A extensão envia só para o app no mesmo computador.
   - URL da política de privacidade: a do passo 0.
5. **Aba "Distribuição":** visibilidade **Não listado** (DP-15-05). Só quem tem o link instala.
6. **Enviar para revisão.**
7. **Depois da aprovação**, anote o **ID do item** (32 letras, na URL do painel) e a **URL pública da página**.

## 2. Edge Add-ons

1. Acesse **https://partner.microsoft.com/dashboard/microsoftedge** e registre-se no programa (é gratuito).
2. **Criar nova extensão** → envie o mesmo zip.
3. Preencha disponibilidade (**Oculto**, o equivalente a "não listado"), propriedades, textos e privacidade com o mesmo conteúdo.
4. **Publicar.** Depois da aprovação, anote o **ID** e a **URL**.

## 3. Ligar o app às lojas (eu faço isso quando você me passar os dados)

Com os dois IDs e as duas URLs em mãos:

1. **`config.py`:**
   - `EXTENSAO_IDS_PERMITIDOS = ("mkcfobdlgdaeplnklpfcioojjgjjoojo", "<ID Chrome>", "<ID Edge>")`
   - `EXTENSAO_URL_CHROME = "<URL Chrome>"` e `EXTENSAO_URL_EDGE = "<URL Edge>"`
2. **Registrar de novo o host de pareamento** (`python -m instalador.registrar_host`, ou gerar e reinstalar o setup), para que o pareamento automático aceite os IDs das lojas.
3. **Gerar o `TranskriptorSetup.exe` de novo:** a página Primeiros passos passa a mostrar **"Adicionar ao Chrome/Edge"**.

## Se a loja recusar

As recusas mais comuns são justificativa de permissão vaga ou política de privacidade inacessível. Responda com os textos de `LOJA.md`. Se pedirem mudança de permissão, **pare e me avise**: isso muda o contrato do SDD (condição de nova consulta).
