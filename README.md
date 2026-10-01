# Language Reactivation Trainer

A small self-contained web app for reactivating French or Spanish vocabulary
and verb conjugation: typed-answer review with typo/accent tolerance, spaced
repetition, and no backend — everything runs in the browser and progress is
stored in `localStorage`.

Built for intermediate/advanced reactivation, not beginners: ~5,000
vocabulary items (top-frequency words, sourced from real corpus data) plus
full conjugation drilling for the 100 most common verbs, **per language**.
Switch languages with the 🇫🇷/🇪🇸 selector in the header — French and Spanish
progress are tracked completely separately (different vocabularies, separate
spaced-repetition state), so you can work on either or both.

See **[DATA_SOURCES.md](./DATA_SOURCES.md)** (French) and
**[DATA_SOURCES_ES.md](./DATA_SOURCES_ES.md)** (Spanish) for exactly where
each word list and conjugation table came from, what was manually verified,
and known gaps. The Spanish example-sentence/full-sentence-fill-in-blank
feature below is not yet built — only French has it so far.

## Features

- **French or Spanish**: pick a language from the 🇫🇷/🇪🇸 selector in the
  header. Everything below — lessons, verbs mode, categories, multiple
  choice, audio — works the same way in both; progress is tracked
  completely separately per language.
- **Lessons**: vocabulary and verbs are grouped into fixed-size lessons in
  real frequency order (so être/avoir/aller show up in Lesson 1, not after
  4,900 other words). Each lesson opens with a short "today we're learning"
  screen — the words/verbs plus an example sentence with translation where
  one exists — before any quiz starts. A lesson's material is introduced
  gradually under the daily new-card cap, and the next lesson only unlocks
  automatically once per calendar day once everything in the current one has
  been introduced at least once. Use the 📖 Lessons picker to jump straight
  to any lesson (locked or not) and study it directly instead of waiting.
  The picker shows a winding lesson path (done/current/locked nodes) for
  nearby lessons, with a "browse all 500" fallback list for jumping further.
- **Gamified stats**: a streak flame, an all-time "gems" count (total correct
  answers), and a daily "hearts" counter (purely decorative — wrong answers
  never lock you out of practicing) in the header.
- **Practice filter**: in Settings, restrict review to vocabulary only, verb
  conjugation only, or both.
- **Answer mode**: typed (accent/typo-tolerant, the default) or multiple
  choice — pick per your preference in Settings.
- **Cooking companion**: an animated inline-SVG bird (idle bob + wing flap)
  cooks through five stages toward a pie for five correct answers in a row
  (chopping → prepping → simmering → assembling → decorating), with a shake
  + "dropped the pan" mishap on a miss and a confetti celebration with two
  friend birds every 5-streak. Purely a fun session combo, doesn't affect
  scheduling.
- **Audio**: 🔊/🐢 buttons use the browser's built-in text-to-speech
  (no server, no API key) to read French aloud — before answering when the
  French form is already shown as text, and after every answer in the
  completion banner.
- **Completion banner**: after each answer, a bottom banner (green/red)
  shows the result and a Continue button — you advance at your own pace
  instead of an auto-timeout.
- **Progress tracking**: the 📊 panel shows a daily streak, today's and
  all-time accuracy, and a 14-day review history.
- **Two quiz types**: plain vocabulary (English ↔ French) and verb conjugation
  drills ("je ___ (aller, présent)" → "vais"), covering présent, passé composé,
  imparfait, futur simple, and subjonctif présent for the top 100 verbs.
- **Full-sentence fill-in-the-blank**: when a word's example sentence is
  available and the exact form being drilled appears in it, the prompt shows
  the whole French sentence with just that word blanked out, plus its English
  translation, instead of the word in isolation. Falls back to the isolated
  word/phrase prompt otherwise (most items, since example coverage is phase 1
  — see DATA_SOURCES.md).
- **Verbs mode**: the 🗣 picker browses the 100 most common verbs, grouped by
  frequency rank. Tapping one opens a lesson screen with its meaning, a short
  structurally-derived usage note (auxiliary, regularity, pronominal), its
  example sentence where one exists, and its full conjugation table across
  all 5 drilled tenses — with a button per tense to practice just that tense's
  6 persons directly, independent of the main lesson path.
- **Categories**: the 🗂 picker groups vocabulary into themes (House & Home,
  Family & People, Food & Drink, Animals, Body & Health, Clothing, Colors,
  Time & Calendar, Weather & Nature, Travel & Places, Work & School, Emotions
  & Feelings) computed from each word's English gloss, so common nouns like
  "maison" are easy to find and study directly instead of waiting for the
  frequency-ordered lesson path to reach them.
- **Direction weighting**: vocabulary defaults to 70% English→French (the
  harder, productive-recall direction) / 30% French→English, adjustable with a
  slider in Settings.
- **Typo/accent-tolerant grading**: an exact match is marked correct
  immediately. A close-but-not-exact answer (wrong/missing accent, one typo)
  shows the correct answer and asks you to self-confirm "I knew this" vs.
  "I didn't" — it never silently auto-accepts a typo as fully correct. A
  clearly wrong answer is marked wrong automatically.
- **SM-2 spaced repetition**: each item (vocab word or a specific verb/tense/
  person conjugation cell) has its own ease factor and interval, scheduled
  with the classic SuperMemo-2 algorithm.
- **New cards per day cap** (default 15, adjustable) so new material doesn't
  outpace what you're actually reviewing.
- **Works fully offline by default**: all state lives in your browser's
  `localStorage`. Clearing site data resets your progress.
- **Optional account + cloud sync**: create an account under 👤 Account to
  sync progress across devices (see "Cloud sync setup" below). Entirely
  optional — the app is fully functional without it.
- **Optional reward image**: on a clean-correct vocabulary answer, briefly
  shows a relevant photo from Unsplash with photographer credit (see "Image
  reward setup" below). Entirely optional — the app works exactly the same
  without it, just without the image.

## Running locally

No build step, no dependencies. From the repo root:

```sh
python3 -m http.server 8000
# then open http://localhost:8000
```

(Any static file server works — `npx serve`, VS Code's Live Server, etc. It
must be served over HTTP, not opened as a `file://` URL, because the app uses
`fetch()` to load the JSON data files.)

## Deploying for free (GitHub Pages)

This repo has no build step, so GitHub Pages can serve it directly:

1. On GitHub, go to **Settings → Pages** for this repository.
2. Under "Build and deployment", set **Source** to **Deploy from a branch**.
3. Set **Branch** to `main` and folder to `/ (root)`, then **Save**.
4. GitHub will publish the site at
   `https://<your-username>.github.io/french-trainer/` within a minute or two.

That's the whole deploy flow — no Actions workflow needed for a static site
like this one.

## Redeploying after edits

Just push to `main`:

```sh
git add -A
git commit -m "your change"
git push
```

GitHub Pages picks up the new commit automatically (usually live within ~1
minute). There's no separate build/deploy command to run.

## Cloud sync setup

Optional. Without this, the app works exactly as before (localStorage only).
With it, you can sign up/in from any browser and your progress follows you.
Uses [Supabase](https://supabase.com) (free tier: 50,000 monthly active
users, 500MB database — far more than one person needs) so there's no server
for you to run or pay for.

1. Create a free account at [supabase.com](https://supabase.com) and a new
   project (pick any name/region/password — you won't need the DB password
   day to day).
2. In your new project, open the **SQL Editor**, paste in the contents of
   [`data/schema.sql`](./data/schema.sql), and run it. This creates the
   `progress` table with Row Level Security so each user can only ever read
   or write their own row.
3. In **Project Settings → API**, copy the **Project URL** and the **anon
   public** key.
4. Edit `js/supabase-config.js` and paste them in:
   ```js
   export const SUPABASE_URL = "https://xxxxx.supabase.co";
   export const SUPABASE_ANON_KEY = "eyJ...";
   ```
   The anon key is meant to be public (it's committed to the repo on
   purpose) — Row Level Security is what actually protects your data, not
   secrecy of this key.
5. Commit and push. Redeploy as usual (see "Redeploying after edits").
6. Optional: in Supabase's **Authentication → Providers → Email** settings,
   you can turn off "Confirm email" if you don't want to click a
   confirmation link after signing up (fine for personal use; leave it on
   for anything more public).

**Limitations (v1)**: last-write-wins sync — no merge across two devices
active at the same time, no password-reset flow yet (delete and recreate
the user from the Supabase dashboard if you get locked out), and no way to
delete your own account from within the app (do it from the Supabase
dashboard's Authentication tab).

## Image reward setup

Optional. Without this, the app works exactly as before, just without the
reward image on a correct vocab answer. Uses [Unsplash](https://unsplash.com/developers)'s
free API (free "Demo" tier: 50 requests/hour, no cost).

1. Create a free account at [unsplash.com/developers](https://unsplash.com/developers)
   and register a new application (the "Demo" tier is fine — no approval
   process needed for personal use).
2. Copy your **Access Key** from the application's page.
3. Edit `js/image-config.js` and paste it in:
   ```js
   export const UNSPLASH_ACCESS_KEY = "your-access-key-here";
   ```
4. Commit and push. Redeploy as usual (see "Redeploying after edits").

**A real trade-off, not a secret**: unlike the Supabase key, this one isn't
protected by any server-side rule — it's a plain request key that anyone
who opens their browser's devtools can read out of a network request and
use against your quota. Unsplash's free Demo tier is explicitly meant for
this kind of client-side use, so the practical downside is small: worst
case, someone exhausts your 50/hour quota and the reward image silently
stops appearing until it resets — not a billing or security incident,
since there's no paid tier being charged. If that trade-off isn't
acceptable to you, leave the key blank.

**Attribution**: every image shown credits the photographer and links to
Unsplash, per Unsplash's API guidelines.

## Editing the data

`data/vocab.json`/`data/verbs.json` (French) and `data/vocab_es.json`/
`data/verbs_es.json` (Spanish) are plain JSON — hand-edit them if you spot
something worth fixing, or re-run the matching `data/build_data*.py` script
(see DATA_SOURCES.md / DATA_SOURCES_ES.md) to regenerate from scratch after
tweaking the pipeline.

## Adding another language

`js/languages.js` is the single place that defines a language: its data file
paths, TTS locale, pronoun set, and tense labels. The internal tense *keys*
(present/passe_compose/imparfait/futur_simple/subjonctif_present) are shared
across every language on purpose — only the label/prefix shown to the user
differs — so the rest of the app never branches on which language is active.
Adding a third language means: building a `vocab_xx.json`/`verbs_xx.json`
pair in the same shape (see either DATA_SOURCES file for the standard this
project holds data to), adding an entry to `LANGUAGES` in `languages.js`,
and adding its infinitive→English-base-verb table in `js/app.js`
(`ENGLISH_VERBS_FR`/`ENGLISH_VERBS_ES` plus `SPECIAL_ENGLISH_FR`/
`SPECIAL_ENGLISH_ES` show the pattern) for the tense-matched English context
under conjugation drills.

## Project structure

```
index.html          # page shell
css/style.css        # styling (light/dark aware)
js/app.js            # session/queue orchestration, grading, UI wiring
js/items.js          # builds the review-item bank from the data files
js/languages.js      # per-language config: data files, TTS locale, pronouns, tense labels
js/lessons.js        # groups items into lessons, in frequency order
js/categories.js     # keyword-based thematic groupings for the 🗂 picker
js/srs.js            # SM-2 scheduler
js/fuzzy.js          # typo/accent-tolerant answer checking
js/cloud.js          # optional Supabase auth + progress sync
js/supabase-config.js # your Supabase project URL/anon key (see Cloud sync setup)
js/images.js         # optional Unsplash reward-image fetch (graceful no-op if unconfigured)
js/image-config.js   # your Unsplash access key (see Image reward setup)
data/vocab.json      # 4,900 French vocabulary words + English gloss(es)
data/verbs.json       # 100 French verbs with full conjugation tables
data/examples.json   # French example sentences for lesson-intro + sentence mode (phase 1 coverage)
data/build_data.py    # reproducible French data-build pipeline (see DATA_SOURCES.md)
data/vocab_es.json    # 4,900 Spanish vocabulary words + English gloss(es)
data/verbs_es.json    # 100 Spanish verbs with full conjugation tables
data/build_data_es.py # reproducible Spanish data-build pipeline (see DATA_SOURCES_ES.md)
data/gen_es_conjugations.js # build-time step build_data_es.py depends on (see DATA_SOURCES_ES.md)
data/schema.sql       # Supabase table + RLS policies for cloud sync
DATA_SOURCES.md       # French: exact sources, licenses, manual verification, gaps
DATA_SOURCES_ES.md    # Spanish: exact sources, licenses, manual verification, gaps
```
