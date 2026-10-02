# AI Assist — what it is and what it isn't

This app is, and stays, a **fully free, fully static site with no server and
no API key** (see README.md). "AI Assist" is an optional, off-by-default
feature that runs a small open-source AI model entirely inside your own
browser tab, using your device's own GPU — not a paid cloud API, and not a
reason for the app to ever cost money to run.

## How it works

- The model is **[Qwen3](https://huggingface.co/Qwen)**, an open-source
  model released by Alibaba. It runs via
  **[WebLLM](https://github.com/mlc-ai/web-llm)**, an open-source project
  that executes LLMs in-browser using **WebGPU** (the browser standard for
  GPU access from web pages).
- Qwen3 was chosen over similarly-sized alternatives (Gemma 3, Llama 3.2)
  specifically because it benchmarks substantially stronger on French and
  Spanish — the two languages this app teaches. On a multilingual reasoning
  benchmark, Qwen3-4B scored roughly 62/100 on French and Spanish vs.
  Gemma-3-4B's roughly 27/100 at the same size.
- Nothing about this ever touches a server. The model downloads straight
  from its host to your browser, and every request after that runs locally.
  No text you type, and no app data, is ever sent anywhere.

## What it costs you, honestly

- **A one-time download** of roughly 0.5–1 GB the first time you turn it
  on (cached afterward in your browser, so it only downloads once).
- **Some of your device's memory and GPU** while a request is running.
- **It requires WebGPU**, which is now supported by Chrome, Edge, Firefox,
  and Safari — but older browser versions, or devices with very limited
  graphics hardware, may not support it. The toggle is simply unavailable
  on devices where this doesn't work; nothing else in the app is affected.
- It is a **small model, not a large cloud AI** — expect it to be slower
  and occasionally less reliable than something like ChatGPT or Claude.
  Every feature built on it is designed to fail safely: if the model is
  unavailable, slow, or gives an unparseable answer, the app silently
  falls back to its existing non-AI behavior rather than breaking.

## Two quality tiers

- **Balanced (Qwen3 1.7B, ~1 GB)** — the default once enabled; noticeably
  smarter, recommended on most laptops and recent phones.
- **Light (Qwen3 0.6B, ~0.5 GB)** — a smaller, faster fallback for older or
  lower-memory devices.

You can switch between them any time in ⚙ Settings → AI Assist.

## What it's used for

1. **Smarter answer grading.** The existing typo/accent-tolerant checker
   (`js/fuzzy.js`) still runs first and is unchanged. Only when it rejects
   an answer *and* AI Assist is on, the model gets one extra chance to
   recognize a genuine paraphrase (e.g. typing "content" when the target
   was "heureux") — and even then, it never auto-accepts silently. It
   routes through the same honesty-test self-confirm prompt ("did you
   actually know this?") already used for close/accent-only matches, now
   labeled with an 🤖 badge so it's clear the AI flagged it, not the exact
   or fuzzy matcher.
2. **Hint escalation.** A "💡 Hint" button appears on typed-answer cards
   when AI Assist is on, giving up to three increasingly direct clues
   without ever stating the answer outright. Without AI Assist, there is
   no AI-generated hint — the app does not attempt a rule-based imitation
   of this, since a genuinely useful contextual hint needs real language
   understanding.
3. **Conversation practice.** A new 💬 panel for open-ended back-and-forth
   practice at your current level, entirely optional, entirely local.

## Honesty notes

- This document, like DATA_SOURCES.md, is meant to be read literally: if
  something above turns out to be inaccurate as browsers or the underlying
  projects change, that's a bug in this file, not an intentional claim.
- The benchmark numbers above are cited from third-party sources at the
  time this feature was built (described in the project's development
  session) and were not independently re-run against this app's models.
