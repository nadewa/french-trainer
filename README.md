# French Reactivation Trainer

A small self-contained web app for reactivating French vocabulary and verb
conjugation: typed-answer review with typo/accent tolerance, spaced repetition,
and no backend — everything runs in the browser and progress is stored in
`localStorage`.

Built for intermediate/advanced reactivation, not beginners: 5,000 vocabulary
items (top-frequency French words, sourced from real corpus data) plus full
conjugation drilling for the 100 most common verbs.

See **[DATA_SOURCES.md](./DATA_SOURCES.md)** for exactly where the word list
and conjugation tables came from, what was manually verified, and known gaps.

## Features

- **Lessons**: vocabulary and verbs are grouped into fixed-size lessons in
  real frequency order (so être/avoir/aller show up in Lesson 1, not after
  4,900 other words). Each lesson opens with a short "today we're learning"
  screen — the words/verbs plus an example sentence with translation where
  one exists — before any quiz starts. A lesson's material is introduced
  gradually under the daily new-card cap, and the next lesson only unlocks
  automatically once per calendar day once everything in the current one has
  been introduced at least once. Use the 📖 Lessons picker to jump straight
  to any lesson (locked or not) and study it directly instead of waiting.
- **Practice filter**: in Settings, restrict review to vocabulary only, verb
  conjugation only, or both.
- **Progress tracking**: the 📊 panel shows a daily streak, today's and
  all-time accuracy, and a 14-day review history.
- **Two quiz types**: plain vocabulary (English ↔ French) and verb conjugation
  drills ("je ___ (aller, présent)" → "vais"), covering présent, passé composé,
  imparfait, futur simple, and subjonctif présent for the top 100 verbs.
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
- **No login, no server**: all state lives in your browser's `localStorage`.
  Clearing site data resets your progress.

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

## Editing the data

`data/vocab.json` and `data/verbs.json` are plain JSON — hand-edit them if you
spot something worth fixing, or re-run `data/build_data.py` (see
DATA_SOURCES.md) to regenerate from scratch after tweaking the pipeline.

## Project structure

```
index.html          # page shell
css/style.css        # styling (light/dark aware)
js/app.js            # session/queue orchestration, grading, UI wiring
js/items.js          # builds the review-item bank from the data files
js/lessons.js        # groups items into lessons, in frequency order
js/srs.js            # SM-2 scheduler
js/fuzzy.js          # typo/accent-tolerant answer checking
data/vocab.json      # 4,900 vocabulary words + English gloss(es)
data/verbs.json       # 100 verbs with full conjugation tables
data/examples.json   # example sentences for the lesson-intro screen (phase 1 coverage)
data/build_data.py    # reproducible data-build pipeline (see DATA_SOURCES.md)
DATA_SOURCES.md       # exact sources, licenses, manual verification, gaps
```
