// Junta os relatórios por worker do axe.spec.js em axe-relatorio.json e imprime o resumo.
"use strict";
const { readdirSync, readFileSync, writeFileSync } = require("node:fs");
const { resolve } = require("node:path");
const dir = __dirname;
const analises = [];
for (const f of readdirSync(dir).filter((n) => /^axe-relatorio\.w\d+\.json$/.test(n))) analises.push(...JSON.parse(readFileSync(resolve(dir, f), "utf8")).analises);
analises.sort((a, b) => a.rotulo.localeCompare(b.rotulo));
writeFileSync(resolve(dir, "axe-relatorio.json"), JSON.stringify({ gerado_em: new Date().toISOString(), analises }, null, 2));
const agg = {};
for (const a of analises) for (const v of a.violacoes) (agg[`${v.id} [${v.impact}]`] = agg[`${v.id} [${v.impact}]`] || { help: v.help, onde: [] }).onde.push(`${a.rotulo} -> ${v.alvos.slice(0, 3).join(" | ")}`);
console.log(`${analises.length} análises; ${Object.keys(agg).length} regras violadas`);
for (const [k, v] of Object.entries(agg)) { console.log(`\n## ${k} — ${v.help}`); for (const o of v.onde) console.log("  " + o); }
