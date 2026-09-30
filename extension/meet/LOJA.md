# Textos da loja — Transkriptor Meet Bridge

Material para a Chrome Web Store e o Edge Add-ons (DP-15-05: item **não listado**; quem publica é o dono da conta). O pacote sai de `python scripts/empacotar_extensao.py` (sem a `key` de desenvolvimento).

## Nome
Transkriptor Meet Bridge

## Descrição curta (até 132 caracteres)
Leva os nomes de quem fala no Google Meet para o Transkriptor do seu computador. Nada sai do seu PC.

## Descrição completa
O Transkriptor grava e transcreve suas reuniões **no seu computador**. Esta extensão entrega a ele quem está falando no Google Meet, com o horário de cada fala, para que a transcrição mostre o nome de cada pessoa em vez de "Falante 1, Falante 2".

- Funciona com as legendas do Meet desligadas na tela.
- Não entra na reunião como participante, não mostra nada para os outros e não altera a chamada.
- Conecta-se sozinha ao aplicativo Transkriptor instalado no mesmo computador.
- Não envia nada para a internet: os dados vão só para o endereço local `127.0.0.1`.

Requer o aplicativo Transkriptor instalado no Windows.

## Justificativa das permissões
- **Acesso a `meet.google.com`:** ler os nomes dos participantes e as legendas geradas pelo Meet durante a chamada.
- **`storage`:** guardar a credencial de pareamento com o aplicativo local.
- **`nativeMessaging`:** parear automaticamente com o aplicativo Transkriptor instalado no computador (host `com.transkriptor.ponte`), sem o usuário copiar códigos.

## Uso único (Single purpose)
Identificar quem fala nas reuniões do Google Meet para a transcrição local feita pelo aplicativo Transkriptor.

## Política de privacidade
Publicar o conteúdo de `docs/PRIVACIDADE-EXTENSAO.md` numa URL pública e informá-la no painel da loja.

## Depois de publicar
1. Copiar o ID atribuído pela loja (Chrome e Edge) para `config.EXTENSAO_IDS_PERMITIDOS`.
2. Copiar as URLs das páginas da loja para `config.EXTENSAO_URL_CHROME` / `EXTENSAO_URL_EDGE`; os primeiros passos passam a mostrar "Adicionar ao Chrome".
3. Registrar de novo o host de pareamento (`python -m instalador.registrar_host`, ou reinstalar) para que `allowed_origins` inclua os IDs da loja.
