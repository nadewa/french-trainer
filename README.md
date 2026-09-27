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
  The picker shows a winding lesson path (done/current/locked nodes) for
  nearby lessons, with a "browse all 500" fallback list for jumping further.
- **Gamified stats**: a streak flame, an all-time "gems" count (total correct
  answers), and a daily "hearts" counter (purely decorative — wrong answers
  never lock you out of practicing) in the header.
- **Practice filter**: in Settings, restrict review to vocabulary only, verb
  conjugation only, or both.
- **Answer mode**: typed (accent/typo-tolerant, the default) or multiple
  choice — pick per your preference in Settings.
- **Cooking companion**: the bird mascot cooks through five stages toward a
  pie for five correct answers in a row (streak resets on a miss); purely a
  fun session combo, doesn't affect scheduling.
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
- **Works fully offline by default**: all state lives in your browser's
  `localStorage`. Clearing site data resets your progress.
- **Optional account + cloud sync**: create an account under 👤 Account to
  sync progress across devices (see "Cloud sync setup" below). Entirely
  optional — the app is fully functional without it.

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
js/cloud.js          # optional Supabase auth + progress sync
js/supabase-config.js # your Supabase project URL/anon key (see Cloud sync setup)
data/vocab.json      # 4,900 vocabulary words + English gloss(es)
data/verbs.json       # 100 verbs with full conjugation tables
data/examples.json   # example sentences for the lesson-intro screen (phase 1 coverage)
data/build_data.py    # reproducible data-build pipeline (see DATA_SOURCES.md)
data/schema.sql       # Supabase table + RLS policies for cloud sync
DATA_SOURCES.md       # exact sources, licenses, manual verification, gaps
```
