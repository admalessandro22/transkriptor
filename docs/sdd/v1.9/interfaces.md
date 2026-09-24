# Interfaces congeladas — SDD v1.9 (design)

Contratos que a implementação não pode reinventar. São planejados, não implementados. Alterar exige emenda em `spec.md`, `tasks.md` e aqui antes do código consumidor.

## 1. Tokens de design

### `design/tokens.json`

```json
{
  "version": 1,
  "color": {
    "dark":  { "bg-0": "#0F1115", "bg-1": "#151821", "text-1": "#E8EAF0", "accent": "#4F8CFF", "...": "..." },
    "light": { "bg-0": "#F5F6F8", "bg-1": "#FFFFFF", "text-1": "#14171F", "accent": "#1F5FD6", "...": "..." },
    "state": { "idle": "#5B6B8C", "recording": "#22C55E", "processing": "#8B5CF6",
               "diarizing": "#F59E0B", "paused": "#64748B", "error": "#EF4444" }
  },
  "type":   { "family-sans": "...", "family-mono": "...", "scale": { "xs": [12, 16], "sm": [13, 18], "md": [14, 20], "lg": [16, 24], "xl": [20, 28], "2xl": [24, 32], "3xl": [32, 40] } },
  "space":  [4, 8, 12, 16, 24, 32, 48, 64],
  "radius": { "sm": 6, "md": 10, "lg": 14, "pill": 999 },
  "elev":   { "1": "0 1px 2px rgba(0,0,0,.24)", "2": "0 8px 24px rgba(0,0,0,.32)", "3": "0 16px 48px rgba(0,0,0,.40)" },
  "motion": { "fast": 120, "base": 180, "slow": 240, "easing": "cubic-bezier(0.2, 0, 0, 1)" },
  "contrast_pairs": [["text-1", "bg-1", 4.5], ["text-2", "bg-1", 4.5], ["text-3", "bg-1", 4.5], ["accent", "bg-1", 4.5], ["on-accent", "accent-fill", 4.5], ["border-strong", "bg-1", 3.0]]
}
```

### `scripts/gerar_tokens.py`

```python
def carregar_tokens(caminho: Path) -> dict: ...
def gerar_css(tokens: dict) -> str          # :root{...} + @media (prefers-color-scheme: light) + [data-theme=...]
def gerar_python(tokens: dict) -> str       # constantes COR_* como tuplas RGB e dict ESTADOS
def contraste(hex_a: str, hex_b: str) -> float
def verificar_contraste(tokens: dict) -> list[str]   # pares abaixo do mínimo
def main(argv: list[str]) -> int            # --check compara saída com arquivos; --write grava
```

Saídas: `static/css/tokens.css` (prefixo `--tk-`) e `design_tokens.py` (módulo sem imports de produto). `estado_icone.py` passa a importar `COR_AGUARDANDO`, `COR_TRANSCREVENDO`, `COR_DIARIZANDO`, `COR_PROCESSANDO`, `COR_ERRO`, `COR_PAUSADO` de `design_tokens` mantendo os nomes públicos atuais.

Teste `tests/test_design_tokens.py`: `gerar_css(tokens) == tokens.css` no disco, `gerar_python(tokens) == design_tokens.py`, `verificar_contraste(tokens) == []`, nenhum hex literal em `static/css/*.css` fora de `tokens.css`.

## 2. Arquivos de front

```
templates/
  base.html            # shell: nav, topbar, statusbar, slot de conteúdo, <link> tokens+app, <script type="module">
  assistente.html      # página Assistente (mantém nome por compatibilidade com testes)
  inicio.html reunioes.html participantes.html configuracoes.html diagnostico.html galeria.html
static/css/
  tokens.css base.css layout.css components.css assistente.css participantes.css inicio.css configuracoes.css
static/assistente.css  # entrada legada: só @import dos arquivos acima (testes existentes leem este caminho)
static/js/
  api.js estado.js tema.js ui.js markdown.js reunioes.js chat.js participantes.js inicio.js configuracoes.js diagnostico.js
static/assistente.js   # entrada legada que importa os módulos; removida quando os testes migrarem
static/icones.svg static/favicon.ico static/icones/bandeja/<estado>.png
design/tokens.json design/icone/transkriptor.svg
```

Regras: `@import` só em `static/assistente.css`; módulos ES sem bundler; nenhum `innerHTML` com dado não escapado (usar `textContent` ou `escapeHtml` já existente); nenhum `element.style.*` para layout (classes `is-*`/`u-*`).

## 3. Contrato de DOM (IDs estáveis para testes E2E)

Mantidos com a mesma semântica: `#chat`, `#input`, `#send`, `#stop`, `#limpar`, `#copiar-resposta`, `#modelo`, `#busca-transcricao`, `#menu-toggle`, `#abrir-participantes`, `#participantes-drawer` (passa a ser `tk-panel`), `#lista-participantes`, `#reuniao-participantes`, `#reuniao-revisao`, `#correcao-cluster`, `#correcao-nome`, `#correcao-revisao`, `#salvar-correcao`, `#desfazer-correcao`, `#exportar-txt`, `#fechar-participantes`, `#participantes-estado`, `#toast-region`, `#codigo`, `#parear`, `#estado` (pareamento).

Mudam de natureza (teste migrado na task indicada): `#transcricao` deixa de ser `<select>` e vira `<ul id="transcricao" role="listbox">` com `li[role=option][data-id]` e `aria-activedescendant` (T-14.B2); `.action-card` vira `.tk-chip[data-intent]` (T-14.B3); `window.confirm` da exportação vira `<dialog id="dialogo-exportar">` com `#confirmar-exportar` (T-14.C3).

Novos: `#statusbar` (`data-estado`), `#tema-toggle`, `#nav` com `a[data-page]`, `#lista-reunioes-estado`, `#dialogo-confirmacao`, `#inicio-estado`, `#inicio-ultima`, `#inicio-protecao`, `#config-form`, `#diag-lista`, `#diag-exportar`, `#retranscrever-lista`.

## 4. API da Central (aditiva)

Todas as rotas continuam sob `verificar_token` e `cabecalhos_privacidade`. Mutações passam por `validar_mutacao_local` e exigem o header secreto.

```python
# app_estado_ui.py (novo; ≤ 500 linhas; sem lock; sem I/O além do índice)
@dataclass(frozen=True)
class SnapshotEstado:
    estado: str            # aguardando|gravando|processando|separando_vozes|pausado|erro
    rotulo: str            # texto do glossário
    fontes: tuple[str, ...]
    processamento: str | None
    protecao: str          # compatible|protected
    ultima_reuniao: dict | None   # {meeting_id, started_at, estado} vindo de indice_transcricoes
    versao: str
    gerado_em: str         # ISO UTC

def snapshot(app) -> SnapshotEstado: ...          # lê atributos; nunca self._lock; nunca conteúdo
def registrar_provedor(fn: Callable[[], SnapshotEstado]) -> None: ...
def provedor_atual() -> Callable[[], SnapshotEstado] | None: ...
```

```
GET  /api/estado                 -> SnapshotEstado como JSON; 503 {"erro": "estado indisponível"} sem provedor
GET  /api/config                 -> {"deteccao_ativa", "diarizacao_ativa", "identificar_minha_voz", "usar_nomes_meet",
                                     "modo_legendas_meet", "criptografar_transcricoes", "protection_mode",
                                     "modelo_whisper", "iniciar_com_windows", "perfil_voz_existe"}
POST /api/config                 -> {"chave": str, "valor": bool|str, "confirmado": bool}; aplica a mesma função
                                    do menu (app_bandeja_menu) e devolve o novo estado; 409 quando exige
                                    confirmação e "confirmado" é falso, com {"consequencia": str}
POST /api/diagnostico            -> executa diagnostico.coletar em thread; {"itens": [...], "erros": n, "avisos": n, "relatorio": path relativo}
GET  /api/diagnostico/exportar   -> text/plain sem PII (diagnostico.exportar_diagnostico)
GET  /api/audios-retidos         -> [{"nome", "mtime", "duracao_seg"}] via retranscritor.listar_audios (sem caminho absoluto)
POST /api/acoes/retranscrever    -> {"nome": str} valida contra a lista; inicia job em thread; 202 {"aceito": true}
POST /api/acoes/aprender-voz     -> {"rotulo": "FALANTE_XX", "nome": str}; persistir_renomeacao_falante; 404 sem centroides
```

Confirmações exigidas (`consequencia` padronizada, mesmo texto na bandeja): pausar detecção, ativar modo protegido, sair, apagar perfil de voz, exportar texto legível.

## 5. Bandeja

```python
# bandeja_icone.py
def imagem_por_estado(estado: str) -> Image   # tenta static/icones/bandeja/<estado>.png; fallback criar_imagem()
# scripts/gerar_icones.py
def renderizar(svg: Path, tamanho: int, estado: str | None) -> Image
def gerar_ico(svg: Path, destino: Path, tamanhos=(16, 20, 24, 32, 48, 256)) -> Path
def gerar_estados(svg: Path, pasta: Path, estados: Mapping[str, tuple[int,int,int]]) -> list[Path]
```

Menu (`app_bandeja_menu._menu`), ordem normativa: estado (desabilitado) · separador · Abrir Transkriptor · Gravação automática (checked) · Separar vozes (checked) · separador · Reuniões ▸ (Abrir pasta, Retranscrever na Central, Participantes na Central) · Configurações ▸ (Minha voz ▸, Google Meet ▸, Proteção ▸, Modelo Whisper ▸, Iniciar com o Windows) · Diagnóstico · separador · Sair. Itens com estado usam `pystray.MenuItem(..., checked=lambda item: ...)`.

## 6. Consentimento (Win32)

Mantém `pedir_consentimento(timeout_seg) -> bool`, `TITULO_DIALOGO`, IDs de controle e o `WNDPROC`. Acrescenta: `def layout_consentimento(dpi: int) -> dict` (função pura com posições/tamanhos escalados, testável sem janela), ícone da classe via `LoadImageW` do `transkriptor.ico`, controle `msctls_progress32` com `PBM_SETPOS` para a contagem, texto da fonte detectada recebido por parâmetro `fontes: Sequence[str] = ()` (nunca título de janela nem nome de participante).

## 7. Extensão

`extension/meet/pairing.css` é cópia gerada de `tokens.css` + regras mínimas (a extensão não pode carregar do app). `scripts/gerar_tokens.py --extensao` escreve o arquivo; teste compara. `manifest.json` ganha `icons` 16/32/48/128 gerados por `gerar_icones.py`.

## 8. Fixtures sintéticas

`tests/e2e/fixtures/central.js` exporta `estado()`, `reunioes(n)`, `resultado()`, `config()`, `diagnostico()` com dados inventados e estáveis; `tests/e2e/helpers.js` exporta `carregarPagina(page, nome, { csp: true })` que serve templates e estáticos reais via `page.route` com a CSP normativa e registra violações em `window.__csp`.

## 9. Responsabilidade por arquivo

| Arquivo novo | Responsabilidade única | Task |
|---|---|---|
| `design/tokens.json`, `scripts/gerar_tokens.py`, `design_tokens.py` | fonte única de tokens | A1 |
| `static/css/*.css`, `static/icones.svg`, `templates/base.html`, `templates/galeria.html` | fundação visual | A2–A3 |
| `static/js/*.js` | módulos da Central | B1–D3 |
| `app_estado_ui.py` | snapshot e provedor de estado | D1 |
| `scripts/gerar_icones.py`, `design/icone/transkriptor.svg` | ícones e marca | E1 |
| `extension/meet/pairing.css` | identidade na extensão | E5 |
| `tests/test_design_tokens.py`, `tests/test_csp_front.py`, `tests/test_app_estado_ui.py`, `tests/test_central_api.py`, `tests/test_orcamento_front.py`, `tests/e2e/*.spec.js` | gates | A1–G1 |
