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
  allier) fixes the highest-impact cases. **Update**: after a user reported
  "petit" showing "kid" instead of "small" in multiple-choice, every one of
  the top 400 words by frequency was manually reviewed for this same issue,
  turning up 24 total (bringing the override list to 43 entries) — including
  three outright data errors, not just ordering, caught by the review and
  confirmed via web search rather than taken on recollection alone: "car"
  had "car" (the vehicle) as its first gloss, which is a false friend — French
  "car" is a conjunction meaning "because/for", never the English word for an
  automobile (that's "voiture"); "super" had only the single, simply wrong
  gloss "sip" (it means "great/awesome", identical to the English slang
  usage); "amis" had only "Amis" (a Taiwanese indigenous ethnic group,
  evidently a Wiktionary extraction mixing up a capitalized proper noun),
  not "friends"; and "frère" incorrectly included "sister" as a sense — it
  never means sister, only "brother". **This still was not done exhaustively
  across all ~5000 words** (400 of ~4,900 reviewed) — the same class of issue
  likely exists further down the frequency list; report anything that looks
  off.
  **Second update**: a separate user report ("pouvoir" showing "power"
  instead of "can"/"be able to") prompted a full review of all 100 verbs'
  gloss[0] — not a frequency-ordered sample this time, every single one,
  since verbs are drilled far more than any individual vocab word. **56 of
  the 100 verbs needed a fix** (bringing the override list to 99 entries) —
  a much higher hit rate than the vocab review, apparently because verb
  entries collided more often with a noun/adjective sense of the same
  written form (e.g. "pouvoir" the noun "power" vs. "pouvoir" the modal
  verb). One, "falloir", wasn't just misordered: its sourced glosses were
  garbled sentence fragments ("We need something", "You have to") rather
  than word-level translations, which would have broken typed-answer
  grading outright, not just confused multiple-choice. Given this hit rate,
  **a similarly thorough pass over the remaining ~4,500 unreviewed vocab
  words is now a real candidate for follow-up**, not just a theoretical risk.
  **Third update**: per an explicit user request to review everything
  rather than sample it, the vocab review was continued past rank 400:
  ranks 400–700 (45 fixes) and 700–1000 (39 fixes), bringing the override
  list to 183 entries. The hit rate held steady at 13–15%, similar to the
  first 400. As before, most fixes were re-ordering a secondary sense
  ahead of the primary one, but several were outright wrong entries, not
  just misordered, and were confirmed via web search rather than taken on
  recollection: "église" wrongly included "mosque" and "synagogue" as
  senses — église specifically means a Christian church, never a mosque or
  synagogue; "rose" listed "blue" before "pink", which is simply incorrect
  (rose never means blue); "chère" — the exact word a user had separately
  flagged confusion over — was missing its common adjective sense
  ("dear"/"expensive") entirely, showing only an archaic noun sense
  ("fare/food"); "gagne" (a conjugated form of the verb "gagner", "wins")
  had leaked into the vocabulary list as its own headword with an entirely
  unrelated gloss ("go"); and "claire" showed only "oyster bed" (obscure
  aquaculture jargon) instead of its common meaning "clear/light/bright".
  **Fourth update**: continued into ranks 1000–1300 (63 more fixes,
  override list now 246 entries), each cross-checked against a
  dictionary source via web search rather than taken on recollection.
  Several were outright wrong, not misordered: "apporter" listed "take"
  as a sense, but apporter never means take away, only bring something
  to a place; "vache" (cow) and "queue" (tail) were both missing their
  core literal meanings entirely, jumping straight to idiomatic/slang
  senses ("mean person", "line/queue"); "abandonner" included
  "accommodate" and "assign", which are not standard translations of
  that verb at all; "titre" was missing "title" itself; "allo" simply
  repeated the French word back ("Allo") rather than translating it
  ("hello", on the phone); "louis" gave "Lewis" — a different name from
  "Louis". **Fifth update**: continued into ranks 1300–1600 (57 more
  fixes, override list now 303 entries). Outright-wrong entries kept
  turning up at a similar rate: "fiancée" was glossed with a moth
  species name ("Large Yellow Underwing") instead of "fiancée"/
  "betrothed"; "loup" (wolf) was missing its own literal core meaning
  entirely, listing only secondary senses (sea bass, masquerade mask);
  "piscine" included "bathroom", which is simply wrong (that's "salle
  de bain"); "tien" gave "your" (a possessive adjective) instead of
  "yours" (the possessive pronoun "tien" actually is); "sophie" gave
  "Sofia", a different name; "remonter" included a typo ("strech")
  among unrelated words; "king" was glossed with an ancient Chinese
  chime-instrument term ("bianqing"); "réaliser" was missing its very
  common colloquial "realize" sense entirely. **Sixth update**:
  continued into ranks 1600–1900 (50 more fixes, override list now 353
  entries). Two **false friends** stand out from this batch, worth
  flagging on their own since they're the kind of error a learner would
  never catch without a native-level check: "sensible" in French means
  "sensitive", never the English "sensible" (reasonable) — the sourced
  gloss led with "feeling" and buried "sensitive" fourth; "large" in
  French means "wide/broad", never the English "large" (big) — the
  sourced gloss led with "abundant" and listed "broad" last. Also
  outright wrong, confirmed via web search for the slang case: "robin"
  was glossed with Chinese characters (罗宾) instead of the name
  "Robin"; "cigarette" was glossed as "smoke"/"whiff" instead of
  "cigarette" itself; "loyer" (rent) wrongly included "salary"/"wage",
  which belong to the unrelated word "salaire". **Seventh update**:
  continued into ranks 1900–2200 (57 more fixes, override list now 410
  entries). Two more false friends, verified via web search: "caution"
  in French means "deposit/security/bail", never English "caution"
  (carefulness) — the sourced gloss led with the false-friend word
  "caution" itself, which actively misleads rather than just omitting
  the real sense; "définitivement" means "permanently/once and for
  all", never English "definitely" — the sourced gloss
  ("conclusively", "definitively") didn't mislead outright but never
  stated the real meaning either. Also outright wrong: "gants"
  (gloves) was glossed as just "Gants", not a translation at all;
  "diane" (the name) was glossed with a butterfly species name
  ("Southern Festoon"); "chirurgien" (surgeon) included the unrelated
  "surgeonfish". **Eighth update**: continued into ranks 2200–2500 (56
  more fixes, override list now 466 entries). The standout this round
  is "collège", one of the most commonly cited French/English false
  friends (verified via web search): it means "middle school" (ages
  11–15), never "high school" or "college" — the sourced gloss offered
  only "high school"/"gymnasium"/"grammar-school", none of them
  correct. Also fixed something more serious than a stylistic gap:
  "enlèvement" (abduction/kidnapping) included "rape" as a gloss, which
  is simply wrong — "rape" in French is "viol", a completely different
  word already correctly present elsewhere in this same list. Verified
  via web search before removing it, given the severity of leaving a
  wrong gloss like that in place. **Ranks 2500–4900 (~2,400 words) are
  still unreviewed.**
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
- **Update**: a user reported "Le film a été incroyable" (être, passé
  composé) as wrong — correctly: a simple past description/opinion like
  "The movie was incredible" is what imparfait ("était") is for in French;
  passé composé is for a specific, bounded, completed occurrence, not a
  general assessment. The whole-word validation above only checks that the
  drilled form appears in the sentence, not that the sentence is the most
  natural choice for that tense, so this class of error isn't caught
  automatically. Confirmed via web search and fixed (replaced with "Ça a
  été rapide !" — a reaction to a specific just-finished event, the
  textbook-natural use of passé composé). Re-reviewed all 30 passé composé
  sentences added in the update above for the same risk and fixed two more
  on inspection: "vouloir" (passé composé carries a "decided to/insisted
  on" nuance, not simple "wanted," which is what the English gloss said —
  fixed the gloss to "She decided to leave early"), and "rester" (added a
  bounding phrase, "pendant les vacances," removing the ambiguity between a
  specific stay and an ongoing arrangement). The other 27 were
  judged, on this same re-review, to already be unambiguous (either
  explicitly time-bounded by an adverb, or a completed-reaction question
  like "Tu as aimé le spectacle ?" — the standard, natural way to ask that
  in French) — but this was reasoning, not independent verification of
  each one, so treat it as lower-confidence than the sourced data above.
- **Full review of all 321 example sentences**: per the same "review
  everything" request above, every example sentence (not a sample) was
  read through end to end. Only one further issue turned up: "verb:manger"'s
  English gloss read "We're eating together this noon," an awkward literal
  phrasing — fixed to "We're eating together at lunch today." The French
  sentence itself ("Nous mangeons ensemble ce midi.") was already correct
  and unchanged.

## Reproducing / regenerating the data

`data/build_data.py` expects the five raw source files (listed above, with
their exact fetch URLs in the script's docstring) in its working directory,
then writes `data/verbs.json` + `data/vocab.json`. Run `python3 build_data.py`
after downloading them. No API keys needed — everything is a plain HTTPS GET.
