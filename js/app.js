import { checkAnswer } from "./fuzzy.js";
import { newCard, schedule, isDue } from "./srs.js";
import { buildItemBank } from "./items.js";

const STATE_KEY = "ft_state_v1";
const DEFAULT_SETTINGS = { dirWeight: 0.7, newPerDay: 15 };

function todayStr(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

function loadState() {
  let raw;
  try {
    raw = JSON.parse(localStorage.getItem(STATE_KEY));
  } catch {
    raw = null;
  }
  if (!raw) raw = {};
  if (!raw.cards) raw.cards = {};
  if (!raw.settings) raw.settings = { ...DEFAULT_SETTINGS };
  if (!raw.newToday || raw.newToday.date !== todayStr()) {
    raw.newToday = { date: todayStr(), count: 0 };
  }
  return raw;
}

function saveState(state) {
  localStorage.setItem(STATE_KEY, JSON.stringify(state));
}

const state = loadState();
let itemsById = new Map();
let queue = [];
let current = null;
let currentDirection = null; // "en2fr" | "fr2en" | null (conj items)
let sessionStats = { correct: 0, total: 0 };
let pendingSelfConfirm = null;

const el = (id) => document.getElementById(id);

function buildQueue(allItems) {
  const now = Date.now();
  const due = [];
  const unseen = [];

  for (const item of allItems) {
    const card = state.cards[item.id];
    if (!card) {
      unseen.push(item);
    } else if (isDue(card, now)) {
      due.push({ item, card });
    }
  }

  due.sort((a, b) => a.card.due - b.card.due);
  unseen.sort((a, b) => a.rank - b.rank);

  const remainingNew = Math.max(0, state.settings.newPerDay - state.newToday.count);
  const freshBatch = unseen.slice(0, remainingNew);

  const combined = due.map((d) => d.item).concat(freshBatch);
  return combined;
}

function pickDirection() {
  return Math.random() < state.settings.dirWeight ? "en2fr" : "fr2en";
}

function renderStats() {
  const now = Date.now();
  const dueCount = Object.values(state.cards).filter((c) => isDue(c, now)).length;
  const newLeft = Math.max(0, state.settings.newPerDay - state.newToday.count);
  el("stat-due").textContent = String(dueCount);
  el("stat-new").textContent = String(newLeft);
  el("stat-session").textContent = `${sessionStats.correct}/${sessionStats.total}`;
}

function promptTextFor(item, direction) {
  if (item.type === "vocab") {
    if (direction === "en2fr") {
      return { prompt: item.gloss.slice(0, 3).join(" / "), hint: "Type the French word." };
    }
    return { prompt: item.word, hint: "Type the English meaning." };
  }
  // conjugation
  const glossHint = item.gloss.slice(0, 2).join("/");
  return {
    prompt: `${item.pronounLabel} ___`,
    hint: `(${item.displayInfinitive} — ${glossHint} — ${item.tenseLabel})`,
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
    queue = buildQueue(Array.from(itemsById.values()));
  }
  if (queue.length === 0) {
    el("card").classList.add("hidden");
    el("done").classList.remove("hidden");
    renderStats();
    return;
  }
  el("card").classList.remove("hidden");
  el("done").classList.add("hidden");

  current = queue.shift();
  currentDirection = current.type === "vocab" ? pickDirection() : null;

  const { prompt, hint } = promptTextFor(current, currentDirection);
  el("prompt").textContent = prompt;
  el("hint").textContent = hint;
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
}

async function boot() {
  const [vocab, verbs] = await Promise.all([
    fetch("data/vocab.json").then((r) => r.json()),
    fetch("data/verbs.json").then((r) => r.json()),
  ]);
  const bank = buildItemBank(vocab, verbs);
  itemsById = new Map(bank.map((i) => [i.id, i]));

  initSettingsUI();
  queue = buildQueue(bank);
  nextCard();

  el("submit-btn").addEventListener("click", submitAnswer);
  el("answer").addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitAnswer();
  });
  el("knew-it").addEventListener("click", () => confirmSelf(true));
  el("didnt-know").addEventListener("click", () => confirmSelf(false));
  el("settings-toggle").addEventListener("click", () => {
    el("settings-panel").classList.toggle("hidden");
  });
  el("restart-btn").addEventListener("click", () => {
    queue = buildQueue(bank);
    sessionStats = { correct: 0, total: 0 };
    nextCard();
  });
}

boot();
