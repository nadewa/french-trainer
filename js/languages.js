// Language packs -- everything that differs between the French and Spanish
// modes (which data files to load, grammatical labels, pronoun sets, TTS
// locale). The internal tense KEYS are shared across languages on purpose
// (both verbs.json and verbs_es.json use the same 5 keys: present,
// passe_compose, imparfait, futur_simple, subjonctif_present) so the rest of
// the app's code never needs to branch on language -- only these packs do.

export const LANGUAGES = {
  fr: {
    code: "fr",
    name: "Français",
    englishName: "French",
    flag: "🇫🇷",
    ttsLang: "fr-FR",
    vocabFile: "data/vocab.json",
    verbsFile: "data/verbs.json",
    examplesFile: "data/examples.json",
    pronouns: ["je", "tu", "il/elle", "nous", "vous", "ils/elles"],
    tenses: [
      { key: "present", label: "présent", prefix: "" },
      { key: "passe_compose", label: "passé composé", prefix: "" },
      { key: "imparfait", label: "imparfait", prefix: "" },
      { key: "futur_simple", label: "futur simple", prefix: "" },
      { key: "subjonctif_present", label: "subjonctif présent", prefix: "que " },
    ],
  },
  es: {
    code: "es",
    name: "Español",
    englishName: "Spanish",
    flag: "🇪🇸",
    ttsLang: "es-ES",
    vocabFile: "data/vocab_es.json",
    verbsFile: "data/verbs_es.json",
    examplesFile: null, // no example-sentence data yet for Spanish -- sentence mode simply never triggers
    pronouns: ["yo", "tú", "él/ella", "nosotros", "vosotros", "ellos/ellas"],
    tenses: [
      { key: "present", label: "presente", prefix: "" },
      { key: "passe_compose", label: "pretérito perfecto", prefix: "" },
      { key: "imparfait", label: "pretérito imperfecto", prefix: "" },
      { key: "futur_simple", label: "futuro simple", prefix: "" },
      { key: "subjonctif_present", label: "subjuntivo presente", prefix: "" },
    ],
  },
};

export const DEFAULT_LANGUAGE = "fr";

export function getLanguage(code) {
  return LANGUAGES[code] || LANGUAGES[DEFAULT_LANGUAGE];
}
