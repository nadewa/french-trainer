#!/usr/bin/env node
/**
 * Build-time step for the Spanish data pipeline, run BEFORE build_data_es.py.
 *
 * spanish-verbs (npm, Apache-2.0) is a conjugation ENGINE, not a sourced
 * lookup table -- and unlike a table, it can't be read from Python directly.
 * This script calls it for every candidate verb infinitive and writes a
 * plain JSON lookup (es_conjugations.json) that build_data_es.py reads in,
 * the same shape a pre-built table like French's Lefff data would have been.
 *
 * Candidate infinitives are Apertium-eng-spa's verb-tagged (vblex/vbser/
 * vbhaver/vbmod) Spanish headwords that also literally appear in the
 * hermitdave/FrequencyWords es_full.txt list -- see DATA_SOURCES_ES.md for
 * why (the engine itself can't tell a real verb from an -ar/-er/-ir-ending
 * noun; Apertium's POS tags are the authoritative source for that).
 *
 * Usage:
 *   npm install spanish-verbs
 *   node gen_es_conjugations.js
 * (expects apertium-eng-spa.dix and es_full.txt in the working directory --
 * see DATA_SOURCES_ES.md #1 and #3 for exact fetch URLs)
 */
const SpanishVerbs = require('spanish-verbs');
const fs = require('fs');

const apertium = fs.readFileSync('apertium-eng-spa.dix', 'utf-8');
const entries = apertium.match(/<e[^>]*>.*?<\/e>/g) || [];

const verbInfinitives = new Set();
for (const e of entries) {
  const rMatch = e.match(/<r>(.*?)<\/r>/);
  if (!rMatch) continue;
  const rRaw = rMatch[1];
  if (rRaw.includes('<b/>') || rRaw.includes('<g>')) continue; // multiword
  if (!/<s n="(vblex|vbser|vbhaver|vbmod)"\/>/.test(rRaw)) continue;
  const word = rRaw.replace(/<[^>]+>/g, '').trim().toLowerCase();
  if (/^[a-záéíóúñü]+$/.test(word) && (word.endsWith('ar') || word.endsWith('er') || word.endsWith('ir'))) {
    verbInfinitives.add(word);
  }
}
console.error(`[apertium] ${verbInfinitives.size} verb infinitives (POS-tagged)`);

const freqWords = new Set();
for (const line of fs.readFileSync('es_full.txt', 'utf-8').split('\n')) {
  const parts = line.trim().split(' ');
  if (parts.length === 2) freqWords.add(parts[0].toLowerCase());
}

const candidates = [...verbInfinitives].filter((v) => freqWords.has(v)).sort();
console.error(`[verbs] ${candidates.length} candidate infinitives (Apertium-tagged AND in frequency list)`);

const TENSES = {
  present: 'INDICATIVE_PRESENT',
  imperfect: 'INDICATIVE_IMPERFECT',
  perfect: 'INDICATIVE_PERFECT',
  future: 'INDICATIVE_FUTURE',
  subjunctive_present: 'SUBJUNCTIVE_PRESENT',
};

const out = {};
let errorCount = 0;
for (const inf of candidates) {
  const table = {};
  let ok = true;
  for (const [key, tenseName] of Object.entries(TENSES)) {
    const forms = [];
    for (let p = 0; p < 6; p++) {
      try {
        forms.push(SpanishVerbs.getConjugation(inf, tenseName, p) || null);
      } catch (e) {
        forms.push(null);
        ok = false;
      }
    }
    table[key] = forms;
  }
  if (!ok) errorCount++;
  out[inf] = table;
}

fs.writeFileSync('es_conjugations.json', JSON.stringify(out));
console.error(`[out] wrote es_conjugations.json (${candidates.length} verbs, ${errorCount} had at least one failed form)`);
