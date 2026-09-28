// Markdown seguro para respostas do assistente (SDD v1.9, T-14.B3):
// títulos, parágrafos, ênfase, código, listas, tabelas, citações e links http(s).
// Todo texto é escapado antes de qualquer marcação; nada de HTML cru.

export function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function inline(texto) {
  let t = texto;
  t = t.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  t = t.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
  return t;
}

function ehLinhaTabela(l) {
  const t = l.trim();
  return t.startsWith('|') && t.endsWith('|') && t.length > 1;
}

function ehSeparadorTabela(l) {
  return /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l.trim());
}

function celulas(l) {
  const t = l.trim().replace(/^\|/, '').replace(/\|$/, '');
  return t.split('|').map((c) => c.trim());
}

/** Converte markdown (já com HTML escapado internamente) em HTML seguro. */
export function renderMarkdown(text) {
  const linhas = escapeHtml(text || '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let i = 0;
  let lista = null; // 'ul' | 'ol'
  const fecharLista = () => { if (lista) { out.push(`</${lista}>`); lista = null; } };
  let paragrafo = [];
  const fecharParagrafo = () => { if (paragrafo.length) { out.push(`<p>${inline(paragrafo.join('<br>'))}</p>`); paragrafo = []; } };

  while (i < linhas.length) {
    const raw = linhas[i];
    const t = raw.trim();

    if (t.startsWith('```')) {
      fecharParagrafo(); fecharLista();
      const lang = t.slice(3).trim().replace(/[^\w-]/g, '');
      const corpo = [];
      i++;
      while (i < linhas.length && !linhas[i].trim().startsWith('```')) { corpo.push(linhas[i]); i++; }
      i++;
      out.push(`<pre><code${lang ? ` class="lang-${lang}"` : ''}>${corpo.join('\n')}</code></pre>`);
      continue;
    }

    if (!t) { fecharParagrafo(); fecharLista(); i++; continue; }

    const hm = t.match(/^(#{1,4})\s+(.*)$/);
    if (hm) { fecharParagrafo(); fecharLista(); const n = Math.min(hm[1].length + 2, 5); out.push(`<h${n}>${inline(hm[2])}</h${n}>`); i++; continue; }

    if (ehLinhaTabela(t) && i + 1 < linhas.length && ehSeparadorTabela(linhas[i + 1])) {
      fecharParagrafo(); fecharLista();
      const cab = celulas(t);
      i += 2;
      const corpo = [];
      while (i < linhas.length && ehLinhaTabela(linhas[i])) { corpo.push(celulas(linhas[i])); i++; }
      const th = cab.map((c) => `<th>${inline(c)}</th>`).join('');
      const trs = corpo.map((r) => `<tr>${cab.map((_, k) => `<td>${inline(r[k] || '')}</td>`).join('')}</tr>`).join('');
      out.push(`<div class="tabela-wrap"><table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`);
      continue;
    }

    if (t.startsWith('&gt;')) {
      fecharParagrafo(); fecharLista();
      const cit = [];
      while (i < linhas.length && linhas[i].trim().startsWith('&gt;')) { cit.push(linhas[i].trim().replace(/^&gt;\s?/, '')); i++; }
      out.push(`<blockquote>${inline(cit.join('<br>'))}</blockquote>`);
      continue;
    }

    const ol = t.match(/^\d+[.)]\s+(.*)$/);
    const ul = t.match(/^[-*•]\s+(.*)$/);
    if (ol || ul) {
      fecharParagrafo();
      const tipo = ol ? 'ol' : 'ul';
      if (lista && lista !== tipo) fecharLista();
      if (!lista) { out.push(`<${tipo}>`); lista = tipo; }
      out.push(`<li>${inline((ol || ul)[1])}</li>`);
      i++;
      continue;
    }

    fecharLista();
    paragrafo.push(t);
    i++;
  }
  fecharParagrafo(); fecharLista();
  return out.join('');
}
