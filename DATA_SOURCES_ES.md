# Data sources — Spanish

Companion to [DATA_SOURCES.md](./DATA_SOURCES.md) (the French data). Nothing in
`data/verbs_es.json` or `data/vocab_es.json` was generated from memory/training
data. Every word, frequency count, and conjugated form was pulled from one of
the open sources below and merged with `data/build_data_es.py` (included for
full reproducibility).

## 1. Word frequency — hermitdave/FrequencyWords

- **Source**: https://github.com/hermitdave/FrequencyWords
- **File used**: `content/2018/es/es_full.txt`
- Same source and method as the French word list (OpenSubtitles-derived word-form
  frequency counts). 1,202,520 raw rows loaded, 1,000,138 after filtering
  non-Spanish-alphabet tokens.

## 2. Verb conjugations — spanish-verbs (npm)

- **Source**: https://www.npmjs.com/package/spanish-verbs
- **License**: Apache-2.0. Part of the RosaeNLG project (the same family as
  `french-verbs`/`french-verbs-lefff`, used for the French data).
- **Important difference from the French pipeline**: this is a rule-based
  conjugation *engine* (`getConjugation(infinitive, tense, person)`), not a
  sourced lookup table like Lefff. It does **not** validate that its input is
  a real verb (`getConjugation('lugar', ...)` silently returns garbage,
  `"lugo"`) — so the authoritative list of which frequency-list tokens are
  real verb infinitives comes from Apertium's part-of-speech tags (#3 below),
  not from this package.
- **Manual verification found real gaps**: the engine's own README says
  "plenty of exceptions still missing," and that proved true. Every one of
  the 100 selected verbs' présent + subjonctif présent forms were reviewed by
  eye (the same standard as French's Lefff spot-check, but exhaustive here
  since real errors turned up immediately — "pensar" produced "pensa"
  instead of "piense"/"piensa"). Imparfait was checked for the 3 Spanish
  verbs with a genuinely irregular imperfect (ser/ir/ver — a closed,
  well-known set) and futur simple was checked against the closed set of
  verbs with an irregular future stem (poder/poner/querer/saber/tener/venir/
  decir/hacer/salir + the two compounds suponer/mantener present in the
  list). **18 of the 100 verbs required a correction** (39 individual
  tense/person arrays total) — baked into `build_data_es.py` as
  `MANUAL_CONJUGATION_OVERRIDE`, applied after generation, documented inline
  in the script with which category each falls into (yo-irregular "-go"
  verbs, e→ie/o→ue/e→i stem changes, "-iar" stress-shift verbs, a g→j
  spelling change, an irregular imperfect, irregular future stems, one
  irregular past participle inherited from a compound verb). The two least
  obvious corrections (sentir's "sintamos"/"sintáis" nosotros/vosotros
  subjunctive pattern, jugar's "juegue" spelling change) were confirmed via
  web search rather than taken on recollection alone.
- **Residual risk, disclosed**: this was a full pass over présent/subjonctif
  for all 100 verbs, and a full pass over imparfait/futur simple against
  known closed irregular sets — not an exhaustive cell-by-cell recheck of
  every tense × person combination for every verb (500 tense/person cells ×
  100 verbs = 3,000 cells; a rarer gap could still remain in passé composé
  participles beyond the ones checked, for example).
- **Reflexive/pronominal verbs are NOT specially handled** in this pass
  (llamarse, quejarse, irse...) — they're conjugated as their base
  non-reflexive infinitive. The French pipeline only special-cased one such
  verb (souvenir); a fuller pass here is left for a future update.
- Spanish always uses "haber" for compound tenses (no être/avoir split like
  French), so there is no auxiliary-selection step in this pipeline.

## 3. English glosses — Apertium eng-spa (primary)

- **Source**: https://github.com/apertium/apertium-eng-spa
  (`apertium-eng-spa.eng-spa.dix`)
- **License**: GPL. A mature, long-running open-source machine-translation
  project; 37,711 raw dictionary entries.
- Used both as the primary gloss source and, via its part-of-speech tags
  (`vblex`/`vbser`/`vbhaver`/`vbmod`), as the authoritative list of real
  Spanish verb infinitives — solving the conjugation engine's inability to
  distinguish real verbs from -ar/-er/-ir-ending nouns (see #2) with sourced
  data rather than a guess.
- Multi-word entries (tagged `<b/>` word-boundary or `<g>` idiom-extension
  markers in the dictionary's XML) are skipped — only single-token entries
  are used, matching the app's per-word vocabulary model.
- Direction-restricted entries (`r="LR"`, English→Spanish only) are excluded
  from the Spanish→English gloss lookup; unrestricted entries and `r="RL"`
  entries are used.

## 4. English glosses — FreeDict spa-eng (fallback)

- **Source**: https://github.com/freedict/fd-dictionaries
  (`spa-eng/spa-eng.tei`)
- **License**: GPL-2.0-or-later.
- **Checked before use, not assumed**: standalone coverage of the top-5,000
  frequency list is only 28% — confirmed too low to serve as a primary
  source (unlike the French pipeline, where a much larger Wiktionary
  extraction was the primary and FreeDict only filled a small ~1,625-word
  gap). Used here only as a fallback for the ~1,395 words Apertium didn't
  cover.
- **A genuine upstream data defect was found and is disclosed, not silently
  parsed around**: some multi-word translations in the raw TEI file have
  literally lost their spaces at the source — e.g. the entry for "tanto"
  contains the literal text `thatmuch`, confirmed by inspecting the raw XML
  (not a parsing bug in `build_data_es.py`). A manual review of all 23
  FreeDict-sourced words in the top 400 by frequency found and fixed 8 such
  cases via `MANUAL_GLOSS_OVERRIDE` (tanto, mucho, dicho, volver, esta,
  anoche, noticias, buscar). **This was not checked exhaustively across all
  ~1,395 FreeDict-sourced words** — the same defect likely exists further
  down the frequency list; a squished-together, oddly-long single English
  "word" in a gloss is the tell.

## 5. Known limitations (read before trusting a gloss blindly)

- **Manual review covered the top ~400 words by frequency**, the same scope
  as the French pipeline's post-launch review (see DATA_SOURCES.md §6). Found
  and fixed via `MANUAL_GLOSS_OVERRIDE`: Apertium tag-leak artifacts ("mí"/
  "ti" showing the literal grammar tag "prpers" instead of a translation),
  a wrong secondary sense shown first ("este" → "east" before "this"), one
  outright wrong sense — "hermano" (brother) incorrectly included "sister",
  the same class of error as French's frère/sister bug, verified false the
  same way (hermano only ever means brother; sister is "hermana") — plus the
  8 FreeDict concatenation defects above. **Not exhaustive** — assume the
  same classes of issue exist further down the list.
- **No lemmatization for non-verb vocabulary**, same gap as French: plurals
  and gendered adjective forms can appear as separate list entries from
  their base form.
- **Verb/vocab selection required a gloss**, same as French: candidates
  without one were skipped in frequency order until the target counts (100
  verbs, 4,900 vocab words) were reached.

## Reproducing / regenerating the data

1. Fetch the four raw source files above (exact URLs in the sections
   above) into `data/`'s working directory.
2. `npm install spanish-verbs`, then `node gen_es_conjugations.js` — a
   build-time step since `spanish-verbs` is a JS engine, not
   Python-importable. Writes `es_conjugations.json`. Verified to reproduce
   the shipped file byte-for-byte from the raw sources.
3. `python3 build_data_es.py` — reads everything above and writes
   `vocab_es.json` + `verbs_es.json`.

No API keys needed anywhere in the pipeline.
