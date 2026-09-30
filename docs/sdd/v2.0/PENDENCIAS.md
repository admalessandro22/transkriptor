# Pendências da v2.0 (atualizado em 2026-09-30)

A branch `sdd-v2.0-nomes-ia-instalador` tem a v2.0 implementada e commitada localmente. Não houve push nem PR. O que falta está abaixo, em ordem.

## Com você (usuário)

1. **Testar o instalador numa máquina limpa.**
   - Ative o Windows Sandbox: num PowerShell **de administrador**, rode `Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All` e reinicie o computador.
   - Clique duas vezes em `instalador\teste-sandbox.wsb`: ele abre `dist\TranskriptorSetup.exe` na máquina descartável.
   - Se o Windows bloquear o instalador, use "Mais informações → Executar assim mesmo".
2. **Publicar a extensão** seguindo `docs/GUIA-PUBLICACAO-EXTENSAO.md`, com o pacote `dist\transkriptor-meet-1.9.0.zip`.
   - Em "Distribuição", marque **não listado**.
   - Depois da aprovação, passe os IDs e as URLs das lojas ao agente.
3. **Reunião de teste com 3 pessoas**, seguindo `docs/sdd/v2.0/evidencias/ROTEIRO-REUNIAO-TESTE.md`. Peça o consentimento de todos antes de gravar.
4. **Se ainda não fez:** recarregue a extensão em `chrome://extensions`, porque o ID fixo agora é `mkcfobdlgdaeplnklpfcioojjgjjoojo`.

## Com o agente (depois dos seus passos)

1. **Com os IDs e as URLs das lojas:**
   - preencher `config.EXTENSAO_IDS_PERMITIDOS`, `EXTENSAO_URL_CHROME` e `EXTENSAO_URL_EDGE`;
   - registrar o host de novo (`python -m instalador.registrar_host`);
   - gerar o Setup outra vez (`ISCC.exe /DVersao=… instalador\transkriptor.iss`).
2. **Depois da reunião de teste:**
   - conferir o Diagnóstico e os nomes;
   - montar o gabarito da T-15.F1, sem copiar texto da reunião;
   - calibrar os limites dos nomes automáticos (exige 3 reuniões).
3. **Planejar o modo de captura de estrutura:** registra só números de campo e tamanhos, sem conteúdo. É ele que destrava:
   - B1W, pedir o idioma da legenda ao Meet;
   - B3, o canal legado;
   - B5, o chat.

   É uma tarefa nova e precisa de aprovação antes de ser escrita. Veja §5 do roteiro.
4. **Decisões do usuário, não do agente:**
   - push/PR/merge da branch;
   - troca de `config.VERSAO`;
   - release.
5. **Opcional:** rodar a suíte inteira de novo (~41 min).
   - Na última execução foram 1233 testes passando e 2 falhando.
   - As duas falhas já foram corrigidas (`cbdc337` e `7ac4366`), e os arquivos afetados foram re-testados.

## Já resolvido nesta sessão (2026-09-30)

- **Instalador:** Inno Setup 6.7.3 instalado; `dist\TranskriptorSetup.exe` gerado (33,2 MB, sem dados pessoais).
- **Pareamento automático registrado neste Windows** (HKCU do Chrome e do Edge) e testado: o ID da extensão é aceito, um ID estranho é recusado. Para desfazer: `python -m instalador.registrar_host --remover`.
- **Bandeja:** não cai mais quando os primeiros passos falham ao abrir (`cbdc337`).
- **Página dos primeiros passos:** sem URL externa no template (`7ac4366`).
- **Recuperação de sessão:** ela renomeava 2 áudios já recuperados com `_02` a cada início, e eles chegaram a 11 repetições (`342d6f7`).
  - Os arquivos estão íntegros, com hash conferido, em `transcricoes/sessoes/<id>/audio/`.
  - Os nomes ficaram longos. Encurtar é opcional e depende do usuário.
- **Bandeja reiniciada às 14:37** com todas as correções.
