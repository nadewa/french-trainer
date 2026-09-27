import { checkAnswer } from "./fuzzy.js";
import { newCard, schedule, isDue } from "./srs.js";
import { buildItemBank, buildIntroRanks } from "./items.js";
import { buildConcepts, groupByLesson } from "./lessons.js";
import * as cloud from "./cloud.js";

const STATE_KEY = "ft_state_v1";
const DEFAULT_SETTINGS = { dirWeight: 0.7, newPerDay: 15, practiceMode: "all" };

function todayStr(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

function normalizeState(raw) {
  if (!raw) raw = {};
  if (!raw.cards) raw.cards = {};
  if (!raw.settings) raw.settings = { ...DEFAULT_SETTINGS };
  for (const k of Object.keys(DEFAULT_SETTINGS)) {
    if (raw.settings[k] === undefined) raw.settings[k] = DEFAULT_SETTINGS[k];
  }
  if (!raw.newToday || raw.newToday.date !== todayStr()) {
    raw.newToday = { date: todayStr(), count: 0 };
  }
  if (!raw.dailyLog) raw.dailyLog = {};
  return raw;
}

function loadState() {
  let raw;
  try {
    raw = JSON.parse(localStorage.getItem(STATE_KEY));
  } catch {
    raw = null;
  }
  return normalizeState(raw);
}

let currentUser = null;
let cloudPushTimer = null;

function scheduleCloudPush() {
  if (!currentUser) return;
  clearTimeout(cloudPushTimer);
  cloudPushTimer = setTimeout(() => {
    cloud
      .pushProgress(currentUser.id, state)
      .then(() => setSyncStatus(`Synced ${new Date().toLocaleTimeString()}`))
      .catch((e) => {
        console.error("cloud push failed", e);
        setSyncStatus("Sync failed — will retry on next change.");
      });
  }, 1500);
}

function setSyncStatus(text) {
  const el2 = document.getElementById("account-sync-status");
  if (el2) el2.textContent = text;
}

function saveState(state) {
  localStorage.setItem(STATE_KEY, JSON.stringify(state));
  scheduleCloudPush();
}

const state = loadState();
let itemsById = new Map();
let bank = [];
let lessonsGrouped = [];
let examplesData = {};
let queue = [];
let current = null;
let currentDirection = null; // "en2fr" | "fr2en" | null (conj items)
let sessionStats = { correct: 0, total: 0 };
let pendingSelfConfirm = null;
let focusLessonIndex = null; // set via the lesson picker to study one lesson directly

const el = (id) => document.getElementById(id);

function matchesPracticeMode(item) {
  const mode = state.settings.practiceMode;
  if (mode === "vocab") return item.type === "vocab";
  if (mode === "conj") return item.type === "conj";
  return true;
}

// Items belonging to a lesson the user hasn't started yet are never eligible as
// "new" cards, regardless of the daily new-card cap -- the lesson intro screen
// (or the lesson picker, for a direct choice) is the only door that opens them.
// When focusLessonIndex is set (via the picker), the queue narrows to just that
// lesson's items and ignores the daily new-card cap -- it's a deliberate choice.
function buildQueue(allItems) {
  const now = Date.now();
  const due = [];
  const unseen = [];

  for (const item of allItems) {
    if (!matchesPracticeMode(item)) continue;
    if (focusLessonIndex !== null && item.lessonIndex !== focusLessonIndex) continue;
    const card = state.cards[item.id];
    if (!card) {
      if (focusLessonIndex !== null || item.lessonIndex < state.unlockedLessons) unseen.push(item);
    } else if (isDue(card, now)) {
      due.push({ item, card });
    }
  }

  due.sort((a, b) => a.card.due - b.card.due);
  unseen.sort((a, b) => a.rank - b.rank);

  const freshBatch =
    focusLessonIndex !== null
      ? unseen
      : unseen.slice(0, Math.max(0, state.settings.newPerDay - state.newToday.count));

  const combined = due.map((d) => d.item).concat(freshBatch);
  return combined;
}

// The next lesson should only be offered once every item already unlocked has
// been introduced at least once -- otherwise hitting the daily new-card cap
// partway through a lesson (a verb alone brings ~28 conjugation-drill items)
// would look identical to having finished it.
function hasUnintroducedUnlockedItems() {
  return bank.some((item) => !state.cards[item.id] && item.lessonIndex < state.unlockedLessons);
}

function hasNextLesson() {
  return !hasUnintroducedUnlockedItems() && state.unlockedLessons < lessonsGrouped.length;
}

// The automatic "done -> start next lesson" prompt is capped to once per
// calendar day ("daily lessons"); the lesson picker bypasses this cap since
// that's an explicit manual choice, not the auto-advance flow.
function canAutoAdvanceToday() {
  return state.lastAutoUnlockDate !== todayStr();
}

function pickDirection() {
  return Math.random() < state.settings.dirWeight ? "en2fr" : "fr2en";
}

function recordOutcome(quality) {
  const day = state.dailyLog[todayStr()] || { correct: 0, total: 0 };
  day.total += 1;
  if (quality >= 3) day.correct += 1;
  state.dailyLog[todayStr()] = day;
}

function computeStreak() {
  const log = state.dailyLog;
  const d = new Date();
  if (!log[todayStr(d)] || log[todayStr(d)].total === 0) {
    d.setDate(d.getDate() - 1);
  }
  let streak = 0;
  while (log[todayStr(d)] && log[todayStr(d)].total > 0) {
    streak++;
    d.setDate(d.getDate() - 1);
  }
  return streak;
}

// Gems and hearts are purely decorative flavor on top of the real SRS/stats
// data -- gems = all-time correct answers (a number that only grows), hearts
// = a playful "mistakes today" counter that never actually blocks practice.
function computeTotals() {
  const log = state.dailyLog;
  return Object.values(log).reduce(
    (acc, d) => ({ correct: acc.correct + d.correct, total: acc.total + d.total }),
    { correct: 0, total: 0 }
  );
}

function computeHearts() {
  const today = state.dailyLog[todayStr()] || { correct: 0, total: 0 };
  const wrongToday = today.total - today.correct;
  return Math.max(0, 5 - wrongToday);
}

function renderStats() {
  const now = Date.now();
  const dueCount = Object.values(state.cards).filter((c) => isDue(c, now)).length;
  const newLeft = Math.max(0, state.settings.newPerDay - state.newToday.count);
  el("stat-due").textContent = String(dueCount);
  el("stat-new").textContent = String(newLeft);
  el("stat-session").textContent = `${sessionStats.correct}/${sessionStats.total}`;
  el("stat-streak").textContent = String(computeStreak());
  el("stat-gems").textContent = String(computeTotals().correct);
  el("stat-hearts").textContent = String(computeHearts());
}

function promptTextFor(item, direction) {
  if (item.type === "vocab") {
    if (direction === "en2fr") {
      return { prompt: item.gloss.slice(0, 3).join(" / "), hint: "Type the French word.", context: "" };
    }
    return { prompt: item.word, hint: "Type the English meaning.", context: "" };
  }
  // conjugation -- show the verb's example sentence (if we have one) as a quick
  // meaning reminder. It's usually in a different tense than the one being
  // drilled here (most are written in the present), so it's a context hint,
  // not a tense-matched translation.
  const glossHint = item.gloss.slice(0, 2).join("/");
  const examples = examplesData[`verb:${item.infinitive}`];
  const context = examples && examples.length ? examples[0].en : "";
  return {
    prompt: `${item.pronounLabel} ___`,
    hint: `(${item.displayInfinitive} — ${glossHint} — ${item.tenseLabel})`,
    context,
  };
}

function nextCard() {
  pendingSelfConfirm = null;
  el("feedback").className = "feedback hidden";
  el("feedback").textContent = "";
  el("self-confirm").classList.add("hidden");
  el("answer").value = "";
  el("answer").disabled = false;
  el("submit-btn").disabled = false;

  if (queue.length === 0) {
    queue = buildQueue(bank);
  }
  if (queue.length === 0) {
    if (focusLessonIndex !== null) {
      el("card").classList.add("hidden");
      el("lesson-intro").classList.add("hidden");
      el("done").classList.remove("hidden");
      el("done-nothing").classList.remove("hidden");
      el("done-next-lesson").classList.add("hidden");
      renderStats();
      return;
    }
    const showNext = hasNextLesson();
    const canAuto = showNext && canAutoAdvanceToday();
    el("card").classList.add("hidden");
    el("lesson-intro").classList.add("hidden");
    el("done").classList.remove("hidden");
    el("done-next-lesson").classList.toggle("hidden", !showNext);
    el("done-nothing").classList.toggle("hidden", showNext);
    if (showNext) {
      el("next-lesson-num").textContent = String(state.unlockedLessons + 1);
      el("next-lesson-num2").textContent = String(state.unlockedLessons + 1);
      el("start-next-lesson-btn").classList.toggle("hidden", !canAuto);
      el("next-lesson-wait-note").classList.toggle("hidden", canAuto);
    }
    renderStats();
    return;
  }
  el("card").classList.remove("hidden");
  el("lesson-intro").classList.add("hidden");
  el("done").classList.add("hidden");

  current = queue.shift();
  currentDirection = current.type === "vocab" ? pickDirection() : null;

  const { prompt, hint, context } = promptTextFor(current, currentDirection);
  el("prompt").textContent = prompt;
  el("hint").textContent = hint;
  el("context").textContent = context;
  el("context").classList.toggle("hidden", !context);
  el("answer").focus();
  renderStats();
}

function targetsFor(item, direction) {
  if (item.type === "vocab") {
    return direction === "en2fr" ? [item.word] : item.gloss;
  }
  return [item.expected, ...item.alternates];
}

function gradeAndSchedule(quality) {
  const card = state.cards[current.id] || newCard();
  const isNew = !state.cards[current.id];
  state.cards[current.id] = schedule(card, quality, Date.now());
  if (isNew) state.newToday.count += 1;
  recordOutcome(quality);
  saveState(state);
}

function showFeedback(verdict, correctText) {
  const fb = el("feedback");
  fb.classList.remove("hidden");
  if (verdict === "exact") {
    fb.className = "feedback correct";
    fb.textContent = "Correct.";
  } else if (verdict === "wrong") {
    fb.className = "feedback wrong";
    fb.textContent = `Not quite. Correct answer: ${correctText}`;
  } else {
    fb.className = "feedback close";
    fb.textContent = `Close — correct answer: ${correctText}`;
  }
}

function submitAnswer() {
  const typed = el("answer").value;
  if (!typed.trim()) return;

  const direction = currentDirection;
  const targets = targetsFor(current, direction);
  const result = checkAnswer(typed, targets);

  el("answer").disabled = true;
  el("submit-btn").disabled = true;
  sessionStats.total += 1;

  if (result.verdict === "exact") {
    sessionStats.correct += 1;
    showFeedback("exact", result.target);
    gradeAndSchedule(5);
    setTimeout(nextCard, 500);
  } else if (result.verdict === "close") {
    showFeedback("close", result.target);
    pendingSelfConfirm = result.target;
    el("self-confirm").classList.remove("hidden");
  } else {
    showFeedback("wrong", result.target);
    gradeAndSchedule(1);
    setTimeout(nextCard, 1400);
  }
}

function confirmSelf(knewIt) {
  sessionStats.correct += knewIt ? 1 : 0;
  el("self-confirm").classList.add("hidden");
  gradeAndSchedule(knewIt ? 4 : 2);
  nextCard();
}

function conceptLabel(concept) {
  if (concept.kind === "verb") {
    return `${concept.displayInfinitive} — ${concept.gloss.slice(0, 3).join(", ")}`;
  }
  return `${concept.word} — ${concept.gloss.slice(0, 3).join(", ")}`;
}

function showLessonIntro(index) {
  const concepts = lessonsGrouped[index] || [];

  el("card").classList.add("hidden");
  el("done").classList.add("hidden");
  el("lesson-intro").classList.remove("hidden");

  el("lesson-title").textContent = `Lesson ${index + 1}`;

  const list = el("lesson-concepts");
  list.innerHTML = "";
  for (const c of concepts) {
    const li = document.createElement("li");
    li.textContent = conceptLabel(c);
    list.appendChild(li);
  }

  const examplesBox = el("lesson-examples");
  examplesBox.innerHTML = "";
  for (const c of concepts) {
    const examples = examplesData[c.key];
    if (!examples || !examples.length) continue;
    for (const ex of examples) {
      const p = document.createElement("p");
      p.className = "example";
      p.innerHTML = `<span class="fr">${ex.fr}</span><br><span class="en">${ex.en}</span>`;
      examplesBox.appendChild(p);
    }
  }

  el("start-lesson-btn").onclick = () => startLesson(index);
}

function startLesson(index, { manual = false } = {}) {
  state.unlockedLessons = Math.max(state.unlockedLessons, index + 1);
  if (!manual) state.lastAutoUnlockDate = todayStr();
  saveState(state);
  focusLessonIndex = null;
  queue = buildQueue(bank);
  nextCard();
}

function studyLessonDirectly(index) {
  focusLessonIndex = index;
  el("focus-lesson-label").textContent = `Lesson ${index + 1}`;
  el("focus-banner").classList.remove("hidden");
  if (state.unlockedLessons <= index) {
    // studying an as-yet-locked lesson directly still counts as a manual
    // unlock, so it never eats into the once-a-day automatic advance
    state.unlockedLessons = Math.max(state.unlockedLessons, index + 1);
    saveState(state);
  }
  el("lesson-picker").classList.add("hidden");
  queue = buildQueue(bank);
  nextCard();
}

function exitFocus() {
  focusLessonIndex = null;
  el("focus-banner").classList.add("hidden");
  queue = buildQueue(bank);
  nextCard();
}

function conceptPreview(concepts) {
  return concepts
    .slice(0, 4)
    .map((c) => (c.kind === "verb" ? c.infinitive : c.word))
    .join(", ");
}

const POS_CLASSES = ["pos-left", "pos-center", "pos-right"];

// The "current" lesson for path purposes: the most recent unlocked one if it
// still has unintroduced items, otherwise the next one waiting to unlock.
function currentPathIndex() {
  for (let i = state.unlockedLessons - 1; i >= 0; i--) {
    const hasUnseen = bank.some((item) => item.lessonIndex === i && !state.cards[item.id]);
    if (hasUnseen) return i;
  }
  return Math.min(state.unlockedLessons, lessonsGrouped.length - 1);
}

function renderPath() {
  const path = el("path");
  path.innerHTML = "";
  const current = currentPathIndex();
  const start = Math.max(0, current - 3);
  const end = Math.min(lessonsGrouped.length - 1, current + 5);

  for (let i = start; i <= end; i++) {
    const concepts = lessonsGrouped[i];
    const wrap = document.createElement("div");
    wrap.className = `path-node-wrap ${POS_CLASSES[i % 3]}`;

    const node = document.createElement("button");
    node.className = "path-node";
    let nodeState = "locked";
    if (i < current) nodeState = "done";
    else if (i === current) nodeState = "current";
    node.classList.add(nodeState);
    node.textContent = nodeState === "done" ? "✓" : nodeState === "locked" ? "🔒" : "★";
    node.onclick = () => studyLessonDirectly(i);
    if (nodeState === "current") {
      const bubble = document.createElement("span");
      bubble.className = "start-bubble";
      bubble.textContent = "START";
      node.appendChild(bubble);
    }
    const label = document.createElement("span");
    label.className = "path-node-label";
    label.textContent = `${i + 1}. ${conceptPreview(concepts)}`;
    node.appendChild(label);

    wrap.appendChild(node);
    path.appendChild(wrap);
  }
}

function renderLessonList() {
  const list = el("lesson-list");
  list.innerHTML = "";
  lessonsGrouped.forEach((concepts, index) => {
    const unlocked = index < state.unlockedLessons;
    const row = document.createElement("div");
    row.className = "lesson-row" + (unlocked ? "" : " locked");

    const label = document.createElement("div");
    label.className = "lesson-row-label";
    label.innerHTML = `<span class="lesson-row-num">Lesson ${index + 1}</span> — <span class="lesson-row-concepts">${conceptPreview(concepts)}…</span>`;

    const btn = document.createElement("button");
    btn.textContent = unlocked ? "Study" : "Unlock & study";
    btn.onclick = () => studyLessonDirectly(index);

    row.appendChild(label);
    row.appendChild(btn);
    list.appendChild(row);
  });
}

function renderStatsView() {
  const log = state.dailyLog;
  const days = Object.keys(log).sort();
  const totals = computeTotals();
  const overallAccuracy = totals.total ? Math.round((totals.correct / totals.total) * 100) : 0;
  const today = log[todayStr()] || { correct: 0, total: 0 };
  const todayAccuracy = today.total ? Math.round((today.correct / today.total) * 100) : 0;
  const learnedCount = Object.values(state.cards).filter((c) => c.repetitions >= 2).length;

  el("stats-summary").innerHTML = `
    <div class="stat-tile"><div class="stat-tile-value">${computeStreak()}🔥</div><div class="stat-tile-label">Day streak</div></div>
    <div class="stat-tile"><div class="stat-tile-value">${todayAccuracy}%</div><div class="stat-tile-label">Today's accuracy (${today.total} reviewed)</div></div>
    <div class="stat-tile"><div class="stat-tile-value">${overallAccuracy}%</div><div class="stat-tile-label">All-time accuracy (${totals.total} reviews)</div></div>
    <div class="stat-tile"><div class="stat-tile-value">${learnedCount}</div><div class="stat-tile-label">Items past initial learning</div></div>
  `;

  const history = el("stats-history");
  history.innerHTML = "";
  const last14 = days.slice(-14).reverse();
  for (const d of last14) {
    const entry = log[d];
    const pct = entry.total ? Math.round((entry.correct / entry.total) * 100) : 0;
    const row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = `
      <span class="history-date">${d.slice(5)}</span>
      <span class="history-bar-track"><span class="history-bar-fill" style="width:${pct}%"></span></span>
      <span class="history-count">${entry.correct}/${entry.total}</span>
    `;
    history.appendChild(row);
  }
  if (!last14.length) {
    history.innerHTML = '<p class="note">No reviews logged yet.</p>';
  }
}

function initSettingsUI() {
  const slider = el("dir-weight");
  const sliderLabel = el("dir-weight-label");
  slider.value = Math.round(state.settings.dirWeight * 100);
  sliderLabel.textContent = `${slider.value}% EN→FR / ${100 - slider.value}% FR→EN`;
  slider.addEventListener("input", () => {
    const v = Number(slider.value);
    state.settings.dirWeight = v / 100;
    sliderLabel.textContent = `${v}% EN→FR / ${100 - v}% FR→EN`;
    saveState(state);
  });

  const newPerDay = el("new-per-day");
  newPerDay.value = state.settings.newPerDay;
  newPerDay.addEventListener("change", () => {
    const v = Math.max(0, Math.min(200, Number(newPerDay.value) || 0));
    state.settings.newPerDay = v;
    newPerDay.value = v;
    saveState(state);
    renderStats();
  });

  const practiceMode = el("practice-mode");
  practiceMode.value = state.settings.practiceMode;
  practiceMode.addEventListener("change", () => {
    state.settings.practiceMode = practiceMode.value;
    saveState(state);
    queue = buildQueue(bank);
    nextCard();
  });
}

function renderAccountUI() {
  const configured = cloud.isConfigured();
  el("account-not-configured").classList.toggle("hidden", configured);
  el("account-signed-out").classList.toggle("hidden", !configured || Boolean(currentUser));
  el("account-signed-in").classList.toggle("hidden", !configured || !currentUser);
  if (currentUser) el("account-email-display").textContent = currentUser.email;
}

// Cloud state fully replaces local state on sign-in (last-write-wins, no
// cross-device merge -- documented in README.md). `state` is a shared const
// referenced by closures throughout the file, so its properties are mutated
// in place rather than reassigning the binding.
function replaceLocalState(raw) {
  const normalized = normalizeState(raw);
  for (const k of Object.keys(state)) delete state[k];
  Object.assign(state, normalized);
}

async function handleSession(session) {
  currentUser = session ? session.user : null;
  if (!currentUser) {
    renderAccountUI();
    return;
  }
  setSyncStatus("Syncing…");
  try {
    const cloudState = await cloud.pullProgress(currentUser.id);
    if (cloudState) {
      replaceLocalState(cloudState);
      saveState(state);
    } else {
      await cloud.pushProgress(currentUser.id, state);
    }
    setSyncStatus(`Synced ${new Date().toLocaleTimeString()}`);
  } catch (e) {
    console.error(e);
    setSyncStatus("Could not sync — check your connection.");
  }
  renderAccountUI();
  migrateUnlockedLessons();
  focusLessonIndex = null;
  queue = buildQueue(bank);
  sessionStats = { correct: 0, total: 0 };
  nextCard();
}

function initAccountUI() {
  el("account-toggle").addEventListener("click", () => {
    el("account-panel").classList.toggle("hidden");
    el("settings-panel").classList.add("hidden");
    el("lesson-picker").classList.add("hidden");
    el("stats-view").classList.add("hidden");
  });
  el("close-account-btn").addEventListener("click", () => el("account-panel").classList.add("hidden"));

  el("account-signup-btn").addEventListener("click", async () => {
    const email = el("account-email").value.trim();
    const password = el("account-password").value;
    el("account-message").textContent = "";
    try {
      await cloud.signUp(email, password);
      el("account-message").textContent = "Account created. Check your email to confirm, then sign in.";
    } catch (e) {
      el("account-message").textContent = e.message;
    }
  });

  el("account-signin-btn").addEventListener("click", async () => {
    const email = el("account-email").value.trim();
    const password = el("account-password").value;
    el("account-message").textContent = "";
    try {
      const data = await cloud.signIn(email, password);
      await handleSession(data.session);
    } catch (e) {
      el("account-message").textContent = e.message;
    }
  });

  el("account-signout-btn").addEventListener("click", async () => {
    await cloud.signOut();
    currentUser = null;
    setSyncStatus("");
    renderAccountUI();
  });

  // Show a sensible default immediately, then refine it once the async
  // session check settles -- if the Supabase library itself fails to load
  // (network hiccup, ad-blocker, offline), the panel should still show the
  // sign-in form rather than silently staying blank.
  renderAccountUI();
  if (cloud.isConfigured()) {
    cloud
      .getSession()
      .then((session) => {
        if (session) handleSession(session);
      })
      .catch((e) => {
        console.error("Could not check Supabase session", e);
        el("account-message").textContent = "Could not reach the sync service — check your connection.";
      });
  }
}

function migrateUnlockedLessons() {
  if (state.unlockedLessons !== undefined) return;
  let maxLesson = -1;
  for (const item of bank) {
    if (state.cards[item.id]) maxLesson = Math.max(maxLesson, item.lessonIndex);
  }
  state.unlockedLessons = maxLesson + 1; // 0 for a genuinely fresh install
  saveState(state);
}

async function boot() {
  const [vocab, verbs, examples] = await Promise.all([
    fetch("data/vocab.json").then((r) => r.json()),
    fetch("data/verbs.json").then((r) => r.json()),
    fetch("data/examples.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  ]);
  examplesData = examples;

  bank = buildItemBank(vocab, verbs);
  itemsById = new Map(bank.map((i) => [i.id, i]));

  const introRank = buildIntroRanks(vocab, verbs);
  const concepts = buildConcepts(vocab, verbs, introRank);
  lessonsGrouped = groupByLesson(concepts);

  migrateUnlockedLessons();

  initSettingsUI();
  initAccountUI();

  el("submit-btn").addEventListener("click", submitAnswer);
  el("answer").addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitAnswer();
  });
  el("knew-it").addEventListener("click", () => confirmSelf(true));
  el("didnt-know").addEventListener("click", () => confirmSelf(false));
  el("settings-toggle").addEventListener("click", () => {
    el("settings-panel").classList.toggle("hidden");
    el("lesson-picker").classList.add("hidden");
    el("stats-view").classList.add("hidden");
    el("account-panel").classList.add("hidden");
  });
  el("restart-btn").addEventListener("click", () => {
    queue = buildQueue(bank);
    sessionStats = { correct: 0, total: 0 };
    nextCard();
  });
  el("start-next-lesson-btn").addEventListener("click", () => {
    showLessonIntro(state.unlockedLessons);
  });
  el("lessons-toggle").addEventListener("click", () => {
    renderPath();
    el("lesson-picker").classList.toggle("hidden");
    el("settings-panel").classList.add("hidden");
    el("stats-view").classList.add("hidden");
    el("account-panel").classList.add("hidden");
  });
  el("close-picker-btn").addEventListener("click", () => {
    el("lesson-picker").classList.add("hidden");
  });
  el("browse-toggle-btn").addEventListener("click", () => {
    const list = el("lesson-list");
    const showing = list.classList.toggle("hidden") === false;
    el("browse-toggle-btn").textContent = showing ? "Hide full list ▴" : "Browse all 500 lessons ▾";
    if (showing) renderLessonList();
  });
  el("stats-toggle").addEventListener("click", () => {
    renderStatsView();
    el("stats-view").classList.toggle("hidden");
    el("settings-panel").classList.add("hidden");
    el("lesson-picker").classList.add("hidden");
    el("account-panel").classList.add("hidden");
  });
  el("close-stats-btn").addEventListener("click", () => {
    el("stats-view").classList.add("hidden");
  });
  el("exit-focus-btn").addEventListener("click", exitFocus);

  if (state.unlockedLessons === 0) {
    showLessonIntro(0);
  } else {
    queue = buildQueue(bank);
    nextCard();
  }
}

boot();
