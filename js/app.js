import { checkAnswer } from "./fuzzy.js";
import { newCard, schedule, isDue } from "./srs.js";
import { buildItemBank, buildIntroRanks } from "./items.js";
import { buildConcepts, groupByLesson } from "./lessons.js";
import { buildCategoryGroups } from "./categories.js";
import * as cloud from "./cloud.js";

const STATE_KEY = "ft_state_v1";
const DEFAULT_SETTINGS = { dirWeight: 0.7, newPerDay: 15, practiceMode: "all", answerMode: "type" };

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
let categoryGroups = [];
let examplesData = {};
let vocabWordPool = [];
let vocabGlossPool = [];
let conjFormPool = [];
let queue = [];
let current = null;
let currentDirection = null; // "en2fr" | "fr2en" | null (conj items)
let sessionStats = { correct: 0, total: 0 };
let pendingSelfConfirm = null;
let focusLessonIndex = null; // set via the lesson picker to study one lesson directly
let focusFilter = null; // set via the category picker: function(item) -> bool

const el = (id) => document.getElementById(id);

function matchesPracticeMode(item) {
  const mode = state.settings.practiceMode;
  if (mode === "vocab") return item.type === "vocab";
  if (mode === "conj") return item.type === "conj";
  return true;
}

function inFocus(item) {
  if (focusLessonIndex !== null) return item.lessonIndex === focusLessonIndex;
  if (focusFilter) return focusFilter(item);
  return true;
}

function focusActive() {
  return focusLessonIndex !== null || focusFilter !== null;
}

// Items belonging to a lesson the user hasn't started yet are never eligible as
// "new" cards, regardless of the daily new-card cap -- the lesson intro screen
// (or the lesson/category picker, for a direct choice) is the only door that
// opens them. Focus mode (lesson or category picker) narrows the queue to just
// the matching items and ignores the daily new-card cap -- a deliberate choice.
function buildQueue(allItems) {
  const now = Date.now();
  const due = [];
  const unseen = [];

  for (const item of allItems) {
    if (!matchesPracticeMode(item)) continue;
    if (!inFocus(item)) continue;
    const card = state.cards[item.id];
    if (!card) {
      if (focusActive() || item.lessonIndex < state.unlockedLessons) unseen.push(item);
    } else if (isDue(card, now)) {
      due.push({ item, card });
    }
  }

  due.sort((a, b) => a.card.due - b.card.due);
  unseen.sort((a, b) => a.rank - b.rank);

  const freshBatch = focusActive()
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

// Browser built-in text-to-speech (no server, no API key, no cost). Voice
// quality/availability is entirely up to the device's OS -- we can only pick
// the best of what's installed, not add a better one. Silently does nothing
// on a browser without SpeechSynthesis support.
//
// The voice list loads asynchronously (sometimes only after "voiceschanged"
// fires, which can be well after page load, especially on mobile), so it's
// cached and refreshed rather than read fresh on every call.
let cachedVoices = [];
if ("speechSynthesis" in window) {
  const loadVoices = () => {
    cachedVoices = window.speechSynthesis.getVoices();
    describeVoices();
  };
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function bestFrenchVoice() {
  const frVoices = cachedVoices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("fr"));
  if (!frVoices.length) return null;
  // On-device ("local") voices are almost always the higher-quality,
  // more natural-sounding ones -- the flat/"robotic" voice users sometimes
  // hear is typically a low-quality fallback voice, or (on some phones) a
  // remote/network voice that can also fail silently when offline.
  return frVoices.find((v) => v.localService) || frVoices[0];
}

// Surfaces exactly which voice(s) the browser reports, in Settings, so a
// "still sounds robotic" report can be diagnosed instead of guessed at --
// e.g. distinguishing "no French voice detected at all" from "a French
// voice is used, but it's not the one the OS's Accessibility settings
// suggest should be available to web pages."
function describeVoices() {
  const debugEl = document.getElementById("voice-debug");
  if (!debugEl) return;
  if (!("speechSynthesis" in window)) {
    debugEl.textContent = "Voices: this browser doesn't support text-to-speech.";
    return;
  }
  const frVoices = cachedVoices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("fr"));
  if (!frVoices.length) {
    debugEl.textContent = "Voices: no French voice reported by this browser yet.";
    return;
  }
  const chosen = bestFrenchVoice();
  const list = frVoices
    .map((v) => `${v.name} (${v.lang}, ${v.localService ? "on-device" : "remote"})`)
    .join("; ");
  debugEl.textContent = `Voices: using "${chosen.name}". All French voices reported: ${list}`;
}

function speakFrench(text, { slow = false } = {}) {
  if (!("speechSynthesis" in window) || !text) return;
  const synth = window.speechSynthesis;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "fr-FR";
  const voice = bestFrenchVoice();
  if (voice) utter.voice = voice;
  utter.rate = slow ? 0.6 : 0.95;
  // Safari (particularly iOS) can silently drop a speak() call made right
  // after cancel() -- only cancel when something is actually queued/playing,
  // and nudge resume() in case the engine got left in a paused state (a
  // known iOS quirk after the tab was backgrounded).
  if (synth.speaking || synth.pending) synth.cancel();
  synth.resume();
  synth.speak(utter);
}

// The French form for a card, independent of which direction it's being
// quizzed in -- always safe to offer for listening once an answer has been
// graded (and, for fr2en vocab, even before -- it's already shown as text).
function audioTextFor(item) {
  return item.type === "vocab" ? item.word : item.expected;
}

// Tense-matched English periphrasis for conjugation drills, e.g. "he/she was
// doing" for faire+imparfait+il/elle. Built from a per-verb {base, particle}
// English mapping (ordinary translation, not sourced data) plus regular
// English inflection rules and a small irregular-verb override table --
// covers all 100 verbs across the 5 drilled tenses.
const EN_PRONOUNS = ["I", "you", "he/she", "we", "you", "they"];

const ENGLISH_VERBS = {
  aller: "go", vouloir: "want", faire: "do", savoir: "know", dire: "say",
  penser: "think", voir: "see", venir: "come", attendre: "wait for",
  croire: "believe", parler: "speak", prendre: "take", regarder: "watch",
  aimer: "like", trouver: "find", laisser: "leave", connaître: "know",
  arrêter: "stop", rester: "stay", appeler: "call", sortir: "go out",
  passer: "pass", partir: "leave", arriver: "arrive", essayer: "try",
  écouter: "listen", demander: "ask", tenir: "hold", revenir: "come back",
  donner: "give", mettre: "put", chercher: "look for", comprendre: "understand",
  travailler: "work", entrer: "enter", oublier: "forget", continuer: "continue",
  vivre: "live", jouer: "play", sentir: "feel", rentrer: "come home",
  aider: "help", tuer: "kill", commencer: "start", espérer: "hope",
  porter: "carry", entendre: "hear", garder: "keep", ouvrir: "open",
  rendre: "give back", sembler: "seem", envoyer: "send", tirer: "pull",
  ignorer: "ignore", mourir: "die", inquiéter: "worry", suivre: "follow",
  bouger: "move", retourner: "go back", souvenir: "remember", marcher: "walk",
  finir: "finish", changer: "change", perdre: "lose", répondre: "answer",
  manger: "eat", occuper: "occupy", boire: "drink", utiliser: "use",
  imaginer: "imagine", dormir: "sleep", manquer: "miss", monter: "go up",
  compter: "count", rappeler: "call back", devenir: "become", toucher: "touch",
  relater: "recount", permettre: "allow", retrouver: "find again",
  apprendre: "learn", quitter: "leave", montrer: "show", poser: "place",
  emmener: "take away", reculer: "back up", jeter: "throw", allier: "combine",
  excuser: "excuse", revoir: "see again", ressembler: "resemble", lire: "read",
  dégager: "clear", servir: "serve", battre: "beat",
};

const IRREGULAR_PP = {
  go: "gone", do: "done", say: "said", see: "seen", come: "come",
  speak: "spoken", take: "taken", find: "found", leave: "left", know: "known",
  hold: "held", give: "given", put: "put", understand: "understood",
  forget: "forgotten", feel: "felt", hear: "heard", keep: "kept", send: "sent",
  eat: "eaten", drink: "drunk", become: "become", lose: "lost", show: "shown",
  throw: "thrown", read: "read", beat: "beaten",
};
const IRREGULAR_GERUND = { die: "dying", stop: "stopping", put: "putting" };

function englishBase(item) {
  const [base, ...rest] = (ENGLISH_VERBS[item.infinitive] || item.gloss[0]).split(" ");
  return { base, particle: rest.join(" ") };
}
function thirdPersonEn(base) {
  if (/[sxz]$/.test(base) || /(sh|ch)$/.test(base)) return base + "es";
  if (/[^aeiou]y$/.test(base)) return base.slice(0, -1) + "ies";
  if (base.endsWith("o")) return base + "es";
  return base + "s";
}
function gerundEn(base) {
  if (IRREGULAR_GERUND[base]) return IRREGULAR_GERUND[base];
  if (base.endsWith("ie")) return base.slice(0, -2) + "ying";
  if (base.endsWith("e") && !base.endsWith("ee")) return base.slice(0, -1) + "ing";
  return base + "ing";
}
function pastParticipleEn(base) {
  if (IRREGULAR_PP[base]) return IRREGULAR_PP[base];
  if (base === "stop") return "stopped";
  if (base.endsWith("e")) return base + "d";
  if (/[^aeiou]y$/.test(base)) return base.slice(0, -1) + "ied";
  return base + "ed";
}

// être/avoir/pouvoir/devoir/falloir are too irregular for the template above
// (be: am/is/are; have: has; can/must/be-necessary-to are modal, no -s form).
const AUX_BE = ["was", "were", "was", "were", "were", "were"];
const AUX_HAVE = ["have", "have", "has", "have", "have", "have"];
const SPECIAL_ENGLISH = {
  "être:present": ["am", "are", "is", "are", "are", "are"],
  "être:imparfait": AUX_BE,
  "être:futur_simple": Array(6).fill("will be"),
  "être:passe_compose": AUX_HAVE.map((a) => `${a} been`),
  "être:subjonctif_present": Array(6).fill("be"),
  "avoir:present": ["have", "have", "has", "have", "have", "have"],
  "avoir:imparfait": Array(6).fill("had"),
  "avoir:futur_simple": Array(6).fill("will have"),
  "avoir:passe_compose": AUX_HAVE.map((a) => `${a} had`),
  "avoir:subjonctif_present": Array(6).fill("have"),
  "pouvoir:present": Array(6).fill("can"),
  "pouvoir:imparfait": Array(6).fill("could"),
  "pouvoir:futur_simple": Array(6).fill("will be able to"),
  "pouvoir:passe_compose": AUX_HAVE.map((a) => `${a} been able to`),
  "pouvoir:subjonctif_present": Array(6).fill("can"),
  "devoir:present": ["have to", "have to", "has to", "have to", "have to", "have to"],
  "devoir:imparfait": Array(6).fill("had to"),
  "devoir:futur_simple": Array(6).fill("will have to"),
  "devoir:passe_compose": AUX_HAVE.map((a) => `${a} had to`),
  "devoir:subjonctif_present": Array(6).fill("have to"),
  "falloir:present": Array(6).fill("is necessary"),
  "falloir:imparfait": Array(6).fill("was necessary"),
  "falloir:futur_simple": Array(6).fill("will be necessary"),
  "falloir:passe_compose": Array(6).fill("has been necessary"),
  "falloir:subjonctif_present": Array(6).fill("be necessary"),
};

function englishPhraseFor(item) {
  const key = `${item.infinitive}:${item.tenseKey}`;
  if (SPECIAL_ENGLISH[key]) return SPECIAL_ENGLISH[key][item.personIdx];
  const { base, particle } = englishBase(item);
  const suffix = particle ? ` ${particle}` : "";
  switch (item.tenseKey) {
    case "present":
      return (item.personIdx === 2 ? thirdPersonEn(base) : base) + suffix;
    case "imparfait":
      return `${AUX_BE[item.personIdx]} ${gerundEn(base)}${suffix}`;
    case "futur_simple":
      return `will ${base}${suffix}`;
    case "passe_compose":
      return `${AUX_HAVE[item.personIdx]} ${pastParticipleEn(base)}${suffix}`;
    case "subjonctif_present":
      return `(that) ${base}${suffix}`;
    default:
      return "";
  }
}

// Frenchword characters -- used to make sure a whole-word match doesn't fire
// inside a longer word (e.g. needle "va" must not match inside "avait").
const FR_WORD_CHAR = "a-zA-ZàâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇœŒæÆ";

function findWholeWord(haystack, needle) {
  if (!needle) return null;
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(?<![${FR_WORD_CHAR}])${escaped}(?![${FR_WORD_CHAR}])`, "i");
  const m = haystack.match(re);
  return m ? { index: m.index, match: m[0] } : null;
}

// A verb's own vocab-meaning card (e.g. "faire" -> "do/make") shares the
// verb's single example sentence, which is stored under "verb:<infinitive>",
// not the card's own "v:<infinitive>" id.
function findExampleFor(item) {
  if (item.type === "conj") {
    const list = examplesData[`verb:${item.infinitive}`];
    return list ? list[0] : null;
  }
  const direct = examplesData[item.id];
  if (direct) return direct[0];
  const asVerb = examplesData[`verb:${item.id.slice(2)}`];
  return asVerb ? asVerb[0] : null;
}

// Builds a full-sentence fill-in-the-blank prompt when `targetWord` (the
// exact surface form being drilled) can be found as a whole word inside the
// item's example sentence -- searching for the literal expected form (rather
// than restricting by tense/person) guarantees the blank is tense-matched by
// construction, since it can only match a sentence actually written in that
// form. Returns null (falls back to the isolated word/phrase prompt) for the
// large majority of items that don't have a matching example.
function sentencePromptFor(item, targetWord) {
  const ex = findExampleFor(item);
  if (!ex) return null;
  const found = findWholeWord(ex.fr, targetWord);
  if (!found) return null;
  const blanked = ex.fr.slice(0, found.index) + "___" + ex.fr.slice(found.index + found.match.length);
  return { blanked, english: ex.en };
}

function promptTextFor(item, direction) {
  if (item.type === "vocab") {
    if (direction === "en2fr") {
      const sentence = sentencePromptFor(item, item.word);
      if (sentence) {
        return {
          prompt: sentence.blanked,
          hint: "Type the missing French word.",
          context: sentence.english,
          sentenceMode: true,
        };
      }
      return { prompt: item.gloss.slice(0, 3).join(" / "), hint: "Type the French word.", context: "" };
    }
    return { prompt: item.word, hint: "Type the English meaning.", context: "" };
  }
  // conjugation -- prefer a full-sentence blank (tense-matched by
  // construction, see sentencePromptFor); otherwise fall back to an
  // isolated pronoun + accurate, tense-matched English translation of the
  // exact person+tense being drilled (e.g. "he/she was doing"), not just
  // the bare infinitive gloss + tense label.
  const sentence = sentencePromptFor(item, item.expected);
  if (sentence) {
    return {
      prompt: sentence.blanked,
      hint: `(${item.displayInfinitive} — ${item.tenseLabel})`,
      context: sentence.english,
      sentenceMode: true,
    };
  }
  const context = `${EN_PRONOUNS[item.personIdx]} ${englishPhraseFor(item)}`;
  return {
    prompt: `${item.pronounLabel} ___`,
    hint: `(${item.displayInfinitive} — ${item.tenseLabel})`,
    context,
  };
}

function nextCard() {
  pendingSelfConfirm = null;
  hideCompletionBanner();
  el("self-confirm").classList.add("hidden");
  el("answer").value = "";
  el("answer").disabled = false;
  el("submit-btn").disabled = false;
  el("choices").innerHTML = "";

  if (queue.length === 0) {
    queue = buildQueue(bank);
  }
  if (queue.length === 0) {
    if (focusActive()) {
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

  const { prompt, hint, context, sentenceMode } = promptTextFor(current, currentDirection);
  el("prompt").textContent = prompt;
  el("prompt").classList.toggle("sentence", !!sentenceMode);
  el("hint").textContent = hint;
  el("context").textContent = context;
  el("context").classList.toggle("hidden", !context);

  // Only offer pre-answer audio when the French form is already shown as
  // text (fr2en vocab) -- for en2fr vocab and all conj items, the French
  // form IS the answer, so playing it early would just give it away.
  const canPreAnswerAudio = current.type === "vocab" && currentDirection === "fr2en";
  el("prompt-speak-btn").classList.toggle("hidden", !canPreAnswerAudio);
  el("prompt-speak-slow-btn").classList.toggle("hidden", !canPreAnswerAudio);
  if (canPreAnswerAudio) {
    el("prompt-speak-btn").onclick = () => speakFrench(current.word);
    el("prompt-speak-slow-btn").onclick = () => speakFrench(current.word, { slow: true });
  }

  if (state.settings.answerMode === "choice") {
    el("answer").classList.add("hidden");
    el("submit-btn").classList.add("hidden");
    el("choices").classList.remove("hidden");
    renderChoices();
  } else {
    el("answer").classList.remove("hidden");
    el("submit-btn").classList.remove("hidden");
    el("choices").classList.add("hidden");
    el("answer").focus();
  }
  renderStats();
}

function renderChoices() {
  const { choices, correctIndex, correctText } = buildChoices(current, currentDirection);
  const box = el("choices");
  box.innerHTML = "";
  choices.forEach((choiceText, idx) => {
    const btn = document.createElement("button");
    btn.className = "choice-btn";
    btn.textContent = choiceText;
    btn.onclick = () => submitChoice(idx, correctIndex, correctText, box);
    box.appendChild(btn);
  });
}

function submitChoice(selectedIndex, correctIndex, correctText, box) {
  const buttons = box.querySelectorAll(".choice-btn");
  buttons.forEach((b) => (b.disabled = true));
  sessionStats.total += 1;

  if (selectedIndex === correctIndex) {
    sessionStats.correct += 1;
    buttons[selectedIndex].classList.add("correct");
    gradeAndSchedule(5);
    showCompletionBanner("exact", correctText);
  } else {
    buttons[selectedIndex].classList.add("incorrect");
    buttons[correctIndex].classList.add("correct");
    gradeAndSchedule(1);
    showCompletionBanner("wrong", correctText);
  }
}

function targetsFor(item, direction) {
  if (item.type === "vocab") {
    return direction === "en2fr" ? [item.word] : item.gloss;
  }
  return [item.expected, ...item.alternates];
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function pickDistractors(pool, exclude, n) {
  const seen = new Set(exclude.map((s) => s.toLowerCase()));
  const picked = [];
  const shuffled = shuffle(pool);
  for (const candidate of shuffled) {
    const key = candidate.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    picked.push(candidate);
    if (picked.length === n) break;
  }
  return picked;
}

// Multiple-choice mode: 1 correct answer + 3 distractors sampled from the
// same kind of pool (other French words, other English glosses, or other
// conjugated forms) so the wrong options are at least plausible.
function buildChoices(item, direction) {
  let correct, pool;
  if (item.type === "vocab") {
    if (direction === "en2fr") {
      correct = item.word;
      pool = vocabWordPool;
    } else {
      correct = item.gloss[0];
      pool = vocabGlossPool;
    }
  } else {
    correct = item.expected;
    pool = conjFormPool;
  }
  const distractors = pickDistractors(pool, [correct], 3);
  const choices = shuffle([correct, ...distractors]);
  return { choices, correctIndex: choices.indexOf(correct), correctText: correct };
}

function gradeAndSchedule(quality) {
  const card = state.cards[current.id] || newCard();
  const isNew = !state.cards[current.id];
  state.cards[current.id] = schedule(card, quality, Date.now());
  if (isNew) state.newToday.count += 1;
  recordOutcome(quality);
  updateCooking(quality);
  saveState(state);
}

// A small session-only "combo" game: five correct answers in a row bakes a
// pie the bird shares with its friends, then starts over. Purely decorative
// -- comboStreak resets on reload, only state.piesBaked (the celebration
// count) persists.
const COOK_CAPTIONS = [
  "Chopping vegetables…",
  "Prepping the mirepoix…",
  "Simmering on the stove…",
  "Assembling the pie…",
  "Decorating beautifully…",
];
let comboStreak = 0;
let cookingMishap = false;

function updateCooking(quality) {
  if (quality >= 3) {
    cookingMishap = false;
    comboStreak++;
    if (comboStreak >= 5) {
      state.piesBaked = (state.piesBaked || 0) + 1;
      renderCookingPanel(true);
      comboStreak = 0;
      return;
    }
  } else {
    cookingMishap = true;
    comboStreak = 0;
  }
  renderCookingPanel(false);
}

function renderCookingPanel(justCelebrated) {
  const sceneEl = el("cooking-scene");
  const captionEl = el("cooking-caption");
  const dotsEl = el("cooking-dots");

  if (justCelebrated) {
    sceneEl.dataset.stage = "celebrate";
    captionEl.textContent = `Pie shared with friends! (${state.piesBaked} baked so far)`;
  } else if (cookingMishap) {
    sceneEl.dataset.stage = "mishap";
    captionEl.textContent = "Oops, dropped the pan — starting over.";
  } else {
    const stageIdx = Math.min(comboStreak, COOK_CAPTIONS.length - 1);
    sceneEl.dataset.stage = String(stageIdx);
    captionEl.textContent = COOK_CAPTIONS[stageIdx];
  }

  dotsEl.innerHTML = "";
  for (let i = 0; i < 5; i++) {
    const dot = document.createElement("span");
    dot.className = "cooking-dot" + (i < comboStreak ? " filled" : "");
    dotsEl.appendChild(dot);
  }
}

// Bottom sliding banner + explicit Continue button, replacing the old
// auto-advance-after-a-timeout pattern -- the user reads at their own pace
// and can hear the French form (whichever direction they were quizzed in)
// before moving on.
let hideBannerTimer = null;

function showCompletionBanner(verdict, correctText) {
  const banner = el("completion-banner");
  const msg = el("completion-message");
  banner.classList.toggle("wrong", verdict === "wrong");
  msg.textContent = verdict === "exact" ? "Correct!" : `Correct answer: ${correctText}`;

  const audioText = audioTextFor(current);
  const speakBtn = el("banner-speak-btn");
  speakBtn.classList.toggle("hidden", !audioText);
  if (audioText) speakBtn.onclick = () => speakFrench(audioText);

  // a fast-following show (e.g. answering again right after Continue) must
  // not let an earlier hide's delayed classList.add("hidden") land after
  // this "show" and re-hide the banner underneath it
  if (hideBannerTimer !== null) {
    clearTimeout(hideBannerTimer);
    hideBannerTimer = null;
  }
  banner.classList.remove("hidden");
  requestAnimationFrame(() => banner.classList.add("show"));
}

function hideCompletionBanner() {
  const banner = el("completion-banner");
  banner.classList.remove("show");
  if (hideBannerTimer !== null) clearTimeout(hideBannerTimer);
  hideBannerTimer = setTimeout(() => {
    banner.classList.add("hidden");
    hideBannerTimer = null;
  }, 250);
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
    gradeAndSchedule(5);
    showCompletionBanner("exact", result.target);
  } else if (result.verdict === "close") {
    pendingSelfConfirm = result.target;
    el("self-confirm-answer").textContent = result.target;
    el("self-confirm").classList.remove("hidden");
  } else {
    gradeAndSchedule(1);
    showCompletionBanner("wrong", result.target);
  }
}

function confirmSelf(knewIt) {
  sessionStats.correct += knewIt ? 1 : 0;
  el("self-confirm").classList.add("hidden");
  gradeAndSchedule(knewIt ? 4 : 2);
  showCompletionBanner(knewIt ? "exact" : "wrong", pendingSelfConfirm);
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
  focusFilter = null;
  queue = buildQueue(bank);
  nextCard();
}

function studyLessonDirectly(index) {
  focusLessonIndex = index;
  focusFilter = null;
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

function studyCategoryDirectly(name, itemIds) {
  focusLessonIndex = null;
  focusFilter = (item) => itemIds.has(item.id);
  el("focus-lesson-label").textContent = name;
  el("focus-banner").classList.remove("hidden");
  el("category-picker").classList.add("hidden");
  queue = buildQueue(bank);
  nextCard();
}

function exitFocus() {
  focusLessonIndex = null;
  focusFilter = null;
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

function renderCategoryList() {
  const list = el("category-list");
  list.innerHTML = "";
  categoryGroups.forEach((group) => {
    const block = document.createElement("button");
    block.className = `category-block category-${group.color}`;
    block.innerHTML = `
      <span class="category-block-icon">${group.icon}</span>
      <span class="category-block-name">${group.name}</span>
      <span class="category-block-count">${group.count} words</span>
    `;
    block.onclick = () => studyCategoryDirectly(group.name, group.itemIds);
    list.appendChild(block);
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
    <div class="stat-tile"><div class="stat-tile-value">${state.piesBaked || 0}🥧</div><div class="stat-tile-label">Pies baked (5-in-a-row streaks)</div></div>
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

  const answerMode = el("answer-mode");
  answerMode.value = state.settings.answerMode;
  answerMode.addEventListener("change", () => {
    state.settings.answerMode = answerMode.value;
    saveState(state);
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
  focusFilter = null;
  queue = buildQueue(bank);
  sessionStats = { correct: 0, total: 0 };
  nextCard();
}

function initAccountUI() {
  el("account-toggle").addEventListener("click", () => {
    el("account-panel").classList.toggle("hidden");
    el("settings-panel").classList.add("hidden");
    el("lesson-picker").classList.add("hidden");
    el("category-picker").classList.add("hidden");
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

  vocabWordPool = bank.filter((i) => i.type === "vocab").map((i) => i.word);
  vocabGlossPool = bank.filter((i) => i.type === "vocab").map((i) => i.gloss[0]);
  conjFormPool = bank.filter((i) => i.type === "conj").map((i) => i.expected);

  const introRank = buildIntroRanks(vocab, verbs);
  const concepts = buildConcepts(vocab, verbs, introRank);
  lessonsGrouped = groupByLesson(concepts);
  categoryGroups = buildCategoryGroups(bank);

  migrateUnlockedLessons();

  initSettingsUI();
  initAccountUI();

  el("submit-btn").addEventListener("click", submitAnswer);
  el("answer").addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitAnswer();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && el("completion-banner").classList.contains("show")) {
      nextCard();
    }
  });
  el("knew-it").addEventListener("click", () => confirmSelf(true));
  el("didnt-know").addEventListener("click", () => confirmSelf(false));
  el("continue-btn").addEventListener("click", () => nextCard());
  el("settings-toggle").addEventListener("click", () => {
    el("settings-panel").classList.toggle("hidden");
    el("lesson-picker").classList.add("hidden");
    el("category-picker").classList.add("hidden");
    el("stats-view").classList.add("hidden");
    el("account-panel").classList.add("hidden");
    if ("speechSynthesis" in window) {
      cachedVoices = window.speechSynthesis.getVoices();
    }
    describeVoices();
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
    el("category-picker").classList.add("hidden");
    el("settings-panel").classList.add("hidden");
    el("stats-view").classList.add("hidden");
    el("account-panel").classList.add("hidden");
  });
  el("close-picker-btn").addEventListener("click", () => {
    el("lesson-picker").classList.add("hidden");
  });
  el("categories-toggle").addEventListener("click", () => {
    renderCategoryList();
    el("category-picker").classList.toggle("hidden");
    el("lesson-picker").classList.add("hidden");
    el("settings-panel").classList.add("hidden");
    el("stats-view").classList.add("hidden");
    el("account-panel").classList.add("hidden");
  });
  el("close-category-btn").addEventListener("click", () => {
    el("category-picker").classList.add("hidden");
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
    el("category-picker").classList.add("hidden");
    el("account-panel").classList.add("hidden");
  });
  el("close-stats-btn").addEventListener("click", () => {
    el("stats-view").classList.add("hidden");
  });
  el("exit-focus-btn").addEventListener("click", exitFocus);

  renderCookingPanel(false);

  if (state.unlockedLessons === 0) {
    showLessonIntro(0);
  } else {
    queue = buildQueue(bank);
    nextCard();
  }
}

boot();
