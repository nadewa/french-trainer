// Local, in-browser AI assist -- entirely optional, opt-in, and runs on the
// user's own device via WebGPU (WebLLM + the open-source Qwen3 model).
// No server, no API key, nothing ever sent anywhere; see AI_ASSIST.md for
// the full explanation this is summarized from.
//
// Every exported "ask the model" function resolves to null (never throws)
// on any failure -- no consent, no WebGPU, load failure, timeout, or
// unparseable output -- so every caller always has a safe non-AI fallback.

const CDN_URL = "https://esm.run/@mlc-ai/web-llm";
// Exact WebLLM prebuilt model ids (mlc-ai/web-llm config) -- Qwen3 was
// chosen over same-size Gemma3/Llama because it benchmarks far stronger on
// French/Spanish specifically, which is what this app needs it for.
const MODELS = {
  balanced: "Qwen3-1.7B-q4f16_1-MLC",
  light: "Qwen3-0.6B-q4f16_1-MLC",
};
const CONSENT_KEY = "ft_ai_consent_v1";
const QUALITY_KEY = "ft_ai_quality_v1";
// Generous: on-device generation (especially on a phone GPU) is much slower
// than a cloud API, and the first call after load also has to pay WebGPU's
// one-time shader-compilation cost (see the warm-up step in getEngine()).
const CALL_TIMEOUT_MS = 30000;
const WARMUP_TIMEOUT_MS = 20000;

let enginePromise = null;
let webllmModulePromise = null;
const progressListeners = new Set();

export function supportsWebGPU() {
  return typeof navigator !== "undefined" && "gpu" in navigator;
}

export function getConsent() {
  try {
    return localStorage.getItem(CONSENT_KEY); // "granted" | "declined" | null
  } catch {
    return null;
  }
}

export function setConsent(value) {
  try {
    localStorage.setItem(CONSENT_KEY, value);
  } catch {
    // ignore -- consent just won't persist across reloads in this case
  }
}

export function getQuality() {
  try {
    return localStorage.getItem(QUALITY_KEY) || "balanced";
  } catch {
    return "balanced";
  }
}

export function setQuality(value) {
  try {
    localStorage.setItem(QUALITY_KEY, value);
  } catch {
    // ignore
  }
  enginePromise = null; // force a reload with the new model on next use
}

export function isEnabled() {
  return supportsWebGPU() && getConsent() === "granted";
}

// Subscribe to model-download progress ({ text, percent }). Returns an
// unsubscribe function.
export function onProgress(fn) {
  progressListeners.add(fn);
  return () => progressListeners.delete(fn);
}

function reportProgress(p) {
  for (const fn of progressListeners) fn(p);
}

async function loadWebLLM() {
  if (!webllmModulePromise) {
    webllmModulePromise = import(CDN_URL);
  }
  return webllmModulePromise;
}

function getEngine() {
  if (!isEnabled()) return null;
  if (!enginePromise) {
    const modelId = MODELS[getQuality()] || MODELS.balanced;
    enginePromise = loadWebLLM()
      .then((webllm) =>
        webllm.CreateMLCEngine(modelId, {
          initProgressCallback: (p) =>
            reportProgress({ text: p.text || "", percent: Math.round((p.progress || 0) * 100) }),
        })
      )
      .then(async (engine) => {
        // WebGPU compiles its shaders lazily on the first real generate
        // call, which can add several extra seconds on top of normal
        // generation time. Pay that cost here, while the loading screen is
        // still up, instead of making the user's first real message (or
        // the first hint/grading check) eat it as an apparent failure.
        reportProgress({ text: "Finishing setup (first run only)…", percent: 100 });
        try {
          await withTimeout(
            engine.chat.completions.create({ messages: [{ role: "user", content: "Bonjour /no_think" }], max_tokens: 4 }),
            WARMUP_TIMEOUT_MS
          );
        } catch (err) {
          console.warn("AI Assist: warm-up generation failed (continuing anyway)", err);
        }
        return engine;
      })
      .catch((err) => {
        enginePromise = null; // allow retrying later instead of staying stuck on a dead promise
        console.error("AI Assist: model load failed", err);
        throw err;
      });
  }
  return enginePromise;
}

// Start (or return the in-flight/already-loaded) engine. Safe to call
// repeatedly; progress is reported via onProgress(). Resolves to null
// rather than rejecting so callers never need a try/catch.
export function preload() {
  const p = getEngine();
  return p ? p.catch(() => null) : Promise.resolve(null);
}

function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((resolve) => setTimeout(() => resolve(null), ms))]);
}

// Qwen3 is a "thinking" model: by default it prefixes its real answer with
// a <think>...</think> reasoning block, which would otherwise show up
// verbatim (in English, breaking immersion) in a learner-facing hint or
// chat reply. "/no_think" is Qwen3's own documented per-turn switch to
// suppress it -- a plain-text convention the model itself was trained to
// respond to, so it works regardless of whether this in-browser runtime
// passes through server-side params like chat_template_kwargs. The regex
// strip below is a safety net for any thinking output that slips through
// anyway (e.g. an older cached build, or the switch being ignored).
function suppressThinking(messages) {
  return messages.map((m, i) => (i === 0 && m.role === "system" ? { ...m, content: `${m.content} /no_think` } : m));
}

function stripThinking(text) {
  let out = text.replace(/<think>[\s\S]*?<\/think>/gi, "");
  out = out.replace(/<think>[\s\S]*$/gi, ""); // an unclosed think block (e.g. cut off by the token limit)
  return out.trim();
}

async function ask(messages) {
  if (!isEnabled()) return null;
  try {
    const engine = await getEngine();
    if (!engine) return null;
    const reply = await withTimeout(
      engine.chat.completions.create({ messages: suppressThinking(messages), temperature: 0.4 }),
      CALL_TIMEOUT_MS
    );
    if (!reply) {
      console.warn(`AI Assist: request timed out after ${CALL_TIMEOUT_MS}ms`);
      return null;
    }
    const raw = reply.choices?.[0]?.message?.content?.trim();
    return raw ? stripThinking(raw) || null : null;
  } catch (err) {
    console.error("AI Assist: request failed", err);
    return null;
  }
}

// Judge whether a typed answer that already failed exact/fuzzy matching is
// still an acceptable paraphrase of the target (e.g. "content" for
// "heureux"). Only ever called on answers the rule-based matcher already
// rejected, so this can only make grading occasionally more lenient, never
// stricter -- and the caller still routes an AI "accept" through the
// existing self-confirm UI rather than silently auto-crediting it.
export async function gradeParaphrase({ typed, target, language, promptText }) {
  const reply = await ask([
    {
      role: "system",
      content:
        `You are grading a ${language} language-learner's free-text answer. ` +
        `Reply with exactly one word: ACCEPT if the learner's answer means ` +
        `essentially the same thing as the target answer (a valid synonym, ` +
        `paraphrase, or minor acceptable variation), or REJECT if it is a ` +
        `different or wrong meaning. No explanation, no punctuation -- only ` +
        `ACCEPT or REJECT.`,
    },
    { role: "user", content: `Prompt: ${promptText}\nTarget answer: ${target}\nLearner's answer: ${typed}` },
  ]);
  if (!reply) return null;
  const verdict = reply.toUpperCase();
  if (verdict.includes("ACCEPT")) return true;
  if (verdict.includes("REJECT")) return false;
  return null; // unparseable output -- treat like "AI unavailable"
}

// One short, progressively more-revealing hint. `level` is 1..3; callers
// should only reach for level 3 once the learner is genuinely stuck, since
// it is allowed to come very close to the answer itself.
export async function generateHint({ word, gloss, language, promptText, level }) {
  const specificity = [
    "vague -- describe the concept or give a related example, without using the word or any close cognate of it",
    "more specific -- you may describe the word's shape, sound, or give a sentence with a blank for it, but still never the word itself",
    "very direct -- you may reveal the first one or two letters and the number of letters",
  ][Math.max(0, Math.min(2, level - 1))];
  return ask([
    {
      role: "system",
      content:
        `You help a ${language} learner who is stuck on a flashcard. Give ONE short ` +
        `hint sentence (max 20 words), in English, at this specificity: ${specificity}. ` +
        `Never say the target word itself.`,
    },
    { role: "user", content: `Prompt shown to learner: ${promptText}\nTarget word/answer: ${word} (${gloss})` },
  ]);
}

// One conversation turn. `history` is an array of prior {role, content}
// turns (role "user" | "assistant"); the system prompt is resent every call
// since the in-browser engine does not persist sessions across page loads.
export async function chatReply({ history, language, levelLabel }) {
  const system = {
    role: "system",
    content:
      `You are a friendly, patient ${language} conversation partner for a learner ` +
      `at ${levelLabel}. Reply ONLY in ${language}. Keep it very short: at most 2 ` +
      `short sentences, simple vocabulary suited to that level -- this is a live ` +
      `chat, not an essay. If the learner made a grammar or word-choice mistake, ` +
      `briefly give the corrected phrase (a few words, not a grammar lecture) ` +
      `before continuing the conversation naturally.`,
  };
  return ask([system, ...history]);
}
