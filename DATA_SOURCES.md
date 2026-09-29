# Data sources

Nothing in `data/verbs.json` or `data/vocab.json` was generated from memory/training
data. Every word, frequency count, and conjugated form was pulled from one of the
open datasets below and merged with `data/build_data.py` (included in this repo
for full reproducibility).

## 1. Word frequency — hermitdave/FrequencyWords

- **Source**: https://github.com/hermitdave/FrequencyWords
- **File used**: `content/2018/fr/fr_full.txt`
- **What it is**: word-form frequency counts derived from the OpenSubtitles corpus
  (subtitle text), one of the most commonly used open French frequency lists.
- **License**: repository code is MIT; the wordlists themselves are a derived,
  freely-redistributed dataset (see repo README).
- 834,768 raw word-form rows were loaded, then filtered down to 759,488 by
  dropping punctuation, digits, and French elision fragments (`j'`, `c'`, `qu'`,
  etc.) that are tokenizer artifacts, not words.

## 2. Verb conjugations — french-verbs-lefff (npm)

- **Source**: https://www.npmjs.com/package/french-verbs-lefff
- **File used**: `dist/conjugations.json` (7,826 verb lemmas, all inflected forms)
- **Underlying resource**: the [Lefff](http://pauillac.inria.fr/~sagot/index.html#lefff)
  (Lexique des Formes Fléchies du Français), a large-scale morphological lexicon
  for French built at Inria/Alexina.
- **License**: LGPL-LR (Lesser General Public License for Linguistic Resources),
  package wrapper Apache-2.0.
- **Manual verification**: spot-checked "être", "aller", "faire", "avoir",
  "pouvoir" present tense, imparfait, futur simple, and subjonctif présent against
  standard French conjugation tables. All matched, including irregulars (e.g.
  "être" → suis/es/est/sommes/êtes/sont; "aller" → vais/vas/va/allons/allez/vont;
  "pouvoir" → puis/peux/peut/pouvons/pouvez/peuvent).
- **Known quirk kept as-is**: Lefff gives "puis" as the je-form of "pouvoir"
  present tense (the traditional/formal form used in inversion, "puis-je"). The
  app additionally accepts "peux" (the modern everyday form) as a correct answer
  for that one cell — this is the only hardcoded alternate-answer in the app.

## 3. Auxiliary verb (être vs. avoir) — french-verbs (npm)

- **Source**: https://www.npmjs.com/package/french-verbs
- Copied *verbatim* the package's hardcoded `listEtre` array (23 verbs that
  always take "être" in compound tenses: aller, apparaître, arriver, décéder,
  devenir, entrer, mourir, naître, partir, rester, revenir, tomber, venir, etc.)
  rather than reconstructing this list from memory, since it's exactly the kind
  of list prone to a subtle omission.
- One case is NOT covered by that list and was fixed by hand: **"souvenir"**
  only exists in modern French as the reflexive "se souvenir" (to remember) —
  every pronominal verb takes "être" in compound tenses, which is a categorical
  French grammar rule, not something the Lefff data encodes (Lefff stores bare
  verb inflections without the reflexive clitic). The app marks it
  `pronominal: true` and builds "je me suis souvenu", "tu t'es souvenu", etc.
  with correct clitic elision.

## 4. English glosses — pquentin/wiktionary-translations (primary)

- **Source**: https://github.com/pquentin/wiktionary-translations
- **File used**: `frwiktionary-20140612-euradicfmt.csv` — French→English
  translations mechanically extracted from a 2014 dump of the French Wiktionary.
- **License**: Wiktionary content is CC BY-SA 3.0 / GFDL.
- 81,630 translation rows, covering 51,259 distinct French headwords.

## 5. English glosses — FreeDict fra-eng (fallback)

- **Source**: https://github.com/freedict/fd-dictionaries (`fra-eng/fra-eng.tei`)
- **License**: GPL-2.0-or-later.
- Used only for the ~1,625 words not found in the Wiktionary extraction (8,505
  headwords total in this dictionary). A couple of entries (e.g. "falloir")
  only had definition-style notes rather than direct translation quotes; those
  notes were used as-is since they're still sourced text, not invented.

## 6. Known limitations (read before trusting a gloss blindly)

- **Verb frequency ranking, not naive counting.** Many 1st-group verbs have a
  present-tense stem spelled identically to an unrelated, far more common noun
  or pronoun — e.g. "armer" (to arm) vs. "arme" (a weapon), "monder" (to hull
  grain) vs. "monde" (world/people), "celer" (to conceal) vs. "cela" (that).
  Naively summing all inflected-form frequencies made these obscure verbs look
  like top-100 words. The build script ranks verbs using only imparfait,
  futur simple, and nous/vous present forms (suffixes like -ais/-erai/-ons
  rarely collide with unrelated common words), which is far more collision
  resistant and produces a plausible top-100 list. This is a heuristic, not a
  perfect fix — it's possible a legitimate but low-imperfect/futur-usage verb
  ranks a little lower than its true frequency deserves.
- **No full lemmatization for non-verb vocabulary.** Verb wordforms are
  correctly folded back to their infinitive (via the Lefff form→lemma index).
  Nouns/adjectives are NOT lemmatized (plurals, feminine forms, etc. can appear
  as separate list entries from their base form) — a proper French lemma
  dictionary wasn't available to fetch in this environment, and heuristic
  stemming (e.g. "strip trailing s") was deliberately avoided because it's
  wrong often enough to introduce bad entries (e.g. "temps", "pays" aren't
  plurals). This is a straightforward but real gap.
- **Dictionary "first sense" isn't always the primary sense.** Both source
  dictionaries list a word's translations in whatever order the original entry
  had them, which is sometimes a rare/technical sense first (e.g. sourced data
  gave "avoir" → "credit balance", "pour" → "pro", "la" → "A" [the musical
  note], "croire" → "accredit"). A small hand-checked override list in
  `build_data.py` (`MANUAL_GLOSS_OVERRIDE`, ~19 entries: mostly function words
  — de/je/pas/le/que/la/vous/tu/à/et/il/ne/on/pour/dans/elle/si/non — plus a
  handful of top verbs — être/avoir/savoir/devoir/croire/regarder/retourner/
  allier) fixes the highest-impact cases. This was NOT done exhaustively across
  all ~5000 words — assume some entries further down the frequency list may
  show a secondary sense first, and cross-check anything that looks off.
- **Verb selection required a gloss.** 2 high-scoring verb lemmas ("ouvrer",
  "saurer" — both archaic/technical) were skipped because no gloss was found
  for them in either dictionary, so the next-ranked verb took their place.
  4,700 candidate vocabulary words were skipped for the same reason before
  reaching 4,900 with a gloss.

## 7. Example sentences — assistant-composed (not corpus-sourced)

- **File**: `data/examples.json`
- Unlike everything above, these are written by the assistant, not pulled from
  an open dataset. Tatoeba (the standard open sentence-pair corpus most
  language apps use for this) and other candidates (Helsinki-NLP/Tatoeba
  Challenge, HuggingFace-hosted sentence datasets, Wikipedia, Openverse) were
  all re-checked and confirmed unreachable from this build environment's
  network policy — only github.com/raw content, npm, and PyPI are allowed
  through, and none of them mirror a usable sentence corpus. Rather than skip
  example sentences entirely, they were written directly using ordinary
  French competence and flagged clearly as such.
- **Coverage**: the 100 highest-frequency vocabulary words get one example
  sentence each (phase 1). The 100 verbs get one example sentence for their
  own vocab meaning, **plus**, for the 30 highest-frequency verbs specifically,
  one additional sentence per drilled tense (présent, passé composé,
  imparfait, futur simple, subjonctif présent) — so the app's full-sentence
  fill-in-the-blank mode (see README) has real coverage across tenses for
  those verbs, not just whichever tense happened to match the single stored
  sentence. Every added sentence was validated programmatically (not just
  proofread) to confirm the exact conjugated form being drilled actually
  appears in it as a whole word, including auxiliary-agreement edge cases
  (e.g. a être-auxiliary past participle written without gender agreement,
  to match the ungendered form the app itself drills and grades against).
  The other 70 verbs and the remaining ~4,800 vocabulary words still have no
  example sentence, and fall back to the isolated word/phrase prompt.

## Reproducing / regenerating the data

`data/build_data.py` expects the five raw source files (listed above, with
their exact fetch URLs in the script's docstring) in its working directory,
then writes `data/verbs.json` + `data/vocab.json`. Run `python3 build_data.py`
after downloading them. No API keys needed — everything is a plain HTTPS GET.
