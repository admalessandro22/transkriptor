# Concept — Transkriptor v1.2.1

**Data:** 2026-07-18  
**Status:** Executado e validado  
**Base:** v1.2 implementada em `docs/sdd/v1.2/`

## North Star

> Ao iniciar o Transkriptor, o usuário vê um único ícone estável na bandeja. Enquanto esse ícone estiver ativo, uma janela real do Google Meet é detectada automaticamente e a transcrição começa sem cliques adicionais.

## Problema

O aplicativo aparenta iniciar: o ícone pisca na bandeja e desaparece. Quando uma reunião do Google Meet começa, a transcrição automática também pode não iniciar. O usuário ainda precisa de um atalho confiável na Área de Trabalho.

## Evidências coletadas em 2026-07-18

1. O processo `pythonw.exe ... transkriptor.pyw` permaneceu vivo desde 2026-07-16, mesmo sem ícone utilizável na bandeja.
2. `transkriptor.pyw` define `self.icone.visible = True` antes de `self.icone.run()`.
3. No backend Win32 do `pystray`, a janela de mensagens (`HWND`) só é criada dentro de `run()`. A configuração antecipada marca o objeto como visível antes de o Windows poder registrar corretamente o ícone.
4. O detector aceita `Reunião - Google Meet`, mas `pygetwindow` lê títulos reais de janelas, por exemplo `... - Google Chrome` e `... — Microsoft Edge`.
5. O padrão atual termina em `Google Meet$`; portanto, `Reunião - Google Meet - Google Chrome` não é reconhecido.
6. A suíte existente passou com **152 testes**, mas não reproduz a ordem de inicialização do `pystray`, títulos reais dos navegadores ou a criação do atalho.

## Hipóteses confirmadas

### H1 — ícone registrado cedo demais

O “pisca e some” é causado pela ordem de inicialização do `pystray`, não pela morte do processo. A correção deve tornar o ícone visível somente no callback de setup executado depois que o loop Win32 estiver pronto.

### H2 — contrato de título diferente do ambiente real

Os testes modelam título de aba, enquanto o produto consome título de janela. O detector deve reconhecer o marcador exato ` - Google Meet` quando seguido pelo fim do título ou por um sufixo de navegador, preservando exclusões e debounce.

## Resultado esperado

- Um único ícone aparece e permanece acessível na bandeja.
- O monitor de Meet começa somente depois que a bandeja está pronta e somente uma vez.
- Chrome e Edge são reconhecidos com seus sufixos reais.
- A transcrição inicia depois das duas confirmações configuradas, em até 15 segundos nas configurações padrão.
- Um atalho `Transkriptor.lnk` abre o app diretamente com `pythonw.exe`, sem console.
- A preferência “Iniciar com o Windows” não é alterada silenciosamente.

## Princípios

1. **Corrigir a causa, não o sintoma.** Não haverá polling para recriar o ícone nem reinício periódico do processo.
2. **TDD obrigatório.** Cada defeito terá um teste que falha antes da correção.
3. **Um proprietário para cada ciclo.** O `pystray` controla o ícone; uma única thread controla a detecção.
4. **Sem regressão de privacidade.** Títulos completos e conteúdo de transcrições não entram nos logs.
5. **Patch pequeno.** Sem trocar framework de bandeja, motor de transcrição ou arquitetura do assistente.

## Fora de escopo

- Substituir `pystray` por Qt, WinUI ou outro framework.
- Fazer o Transkriptor abrir automaticamente ao detectar Meet quando o app não estiver em execução.
- Alterar Whisper, diarização, Ollama, criptografia ou extensão Chrome.
- Ativar “Iniciar com o Windows” sem ação explícita do usuário.
- Criar instalador MSI.
