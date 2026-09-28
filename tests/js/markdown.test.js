import { describe, expect, it } from "vitest";
import { renderMarkdown, escapeHtml } from "../../static/js/markdown.js";


describe("markdown do assistente", () => {
  it("tabela vira table com cabeçalho e linhas", () => {
    const html = renderMarkdown("| Tarefa | Prazo |\n|---|---|\n| Integração | sexta |\n| Revisão | quinta |");
    expect(html).toContain("<table>");
    expect(html).toContain("<th>Tarefa</th>");
    expect(html).toContain("<td>sexta</td>");
    expect((html.match(/<tr>/g) || []).length).toBe(3);
  });

  it("html é escapado antes de qualquer marcação", () => {
    const html = renderMarkdown("<img src=x onerror=alert(1)> **ok**");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
    expect(html).toContain("<strong>ok</strong>");
    expect(escapeHtml('"<>&')).toBe("&quot;&lt;&gt;&amp;");
  });

  it("links só http(s), com noopener e nova aba; javascript: não vira link", () => {
    const ok = renderMarkdown("veja [docs](https://exemplo.local/x) e https://a.b/c");
    expect(ok).toContain('href="https://exemplo.local/x" target="_blank" rel="noopener noreferrer"');
    expect(ok).toContain('href="https://a.b/c"');
    const ruim = renderMarkdown("[x](javascript:alert(1))");
    expect(ruim).not.toContain("<a");
  });

  it("código em bloco preserva conteúdo cru e listas fecham corretamente", () => {
    const html = renderMarkdown("```js\nconst a = 1 < 2;\n```\n\n- um\n- dois\n\n1. tres\n\nfim");
    expect(html).toContain('<pre><code class="lang-js">const a = 1 &lt; 2;</code></pre>');
    expect(html).toContain("<ul><li>um</li><li>dois</li></ul>");
    expect(html).toContain("<ol><li>tres</li></ol>");
    expect(html).toContain("<p>fim</p>");
  });

  it("títulos, citação e parágrafos", () => {
    const html = renderMarkdown("## Resumo\n\n> citação\n> continua\n\nlinha 1\nlinha 2");
    expect(html).toContain("<h4>Resumo</h4>");
    expect(html).toContain("<blockquote>citação<br>continua</blockquote>");
    expect(html).toContain("<p>linha 1<br>linha 2</p>");
  });

  it("render incremental é prefixo-estável: o texto parcial rende sem erro", () => {
    const completo = "| a | b |\n|---|---|\n| 1 | 2 |\n\ntexto";
    for (let i = 1; i <= completo.length; i++) expect(() => renderMarkdown(completo.slice(0, i))).not.toThrow();
    expect(renderMarkdown(completo)).toContain("<table>");
  });
});
