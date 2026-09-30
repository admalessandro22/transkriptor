# Política de privacidade — Transkriptor Meet Bridge

Última atualização: 29/09/2026.

A extensão **Transkriptor Meet Bridge** existe para uma coisa: entregar ao aplicativo **Transkriptor instalado no seu próprio computador** quem está falando numa chamada do Google Meet, para que a transcrição local mostre o nome de cada pessoa.

## O que a extensão lê

- **Onde age:** somente em páginas `https://meet.google.com/*`.
- **O que lê:**
  - os nomes exibidos dos participantes da chamada;
  - as legendas geradas pelo próprio Google Meet (quem falou, o texto e o horário);
  - o idioma das legendas;
  - qual dispositivo da chamada é o seu;
  - as mensagens do chat, quando essa opção está ligada no aplicativo.
- **O que não altera:** nenhum conteúdo da reunião, e nada aparece para os outros participantes.

## Para onde os dados vão

- **Destino único:** o aplicativo Transkriptor no mesmo computador, pelo endereço local `127.0.0.1` e pelo mecanismo de mensagens nativas do navegador.
- **Nada vai para outro lugar:** a extensão **não envia** nenhum dado para servidores da internet, para os desenvolvedores nem para terceiros.
- **Nada é vendido nem usado para publicidade**, e a extensão não coleta dados de navegação fora do Google Meet.

## O que fica guardado no navegador

Apenas a credencial de pareamento com o aplicativo local (`chrome.storage.local`). Ela expira em 90 dias sem uso e pode ser apagada removendo a extensão.

## No aplicativo

- **Onde ficam os dados:** o Transkriptor guarda as transcrições e os eventos das reuniões no seu computador, com a proteção que você escolher nas Configurações.
- **Envio para fora (opcional):** só acontece se **você** configurar uma chave do OpenRouter para resumos ou para o assistente. Nesse caso, o texto da transcrição é enviado para o OpenRouter, depois de um consentimento explícito. Áudio e voz nunca saem do computador.

## Permissões

| Permissão | Por quê |
|---|---|
| `https://meet.google.com/*` | Ler nomes e legendas da chamada. |
| `storage` | Guardar a credencial de pareamento com o aplicativo local. |
| `nativeMessaging` | Parear automaticamente com o aplicativo Transkriptor instalado neste computador. |

## Contato

Dúvidas sobre privacidade: abra uma solicitação no repositório do projeto.
