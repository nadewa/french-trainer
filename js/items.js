// Builds the full review-item bank from the sourced data files. Generalized
// to work for any language pack (see js/languages.js) -- PRONOUNS and TENSES
// used to be French-only module constants; they're now passed in per call so
// the same code drives both French and Spanish.

import { lessonIndexForRank } from "./lessons.js";

// A handful of verbs have more than one commonly-accepted present-day form for
// a given cell; the sourced data only records one. Documented in DATA_SOURCES.md.
const ALTERNATES = {
  "pouvoir:present:0": ["peux"], // "je peux" (modern) alongside sourced "je puis" (formal)
};

const VOWEL_SOUND = /^[aeiouyàâäéèêëïîôöùûü]/i;

function withPrefix(prefix, word) {
  if (!prefix) return word;
  if (prefix === "que " && VOWEL_SOUND.test(word)) return `qu'${word}`;
  return `${prefix}${word}`;
}

export function pronounFor(tense, personIdx, verb, lang) {
  const base = verb.pronominal
    ? `${lang.pronouns[personIdx]} ${verb.reflexive_pronouns[personIdx]}`
    : lang.pronouns[personIdx];
  return withPrefix(tense.prefix, base);
}

// Both plain vocab words and verbs carry a real corpus-frequency number, so they
// can be interleaved into a single "how common is this" order for introducing new
// cards -- without this, all 100 verbs (many of them, like etre/avoir/aller, among
// the most frequent words) would only be reached after all ~4900 plain
// vocab words, which is backwards.
export function buildIntroRanks(vocab, verbs) {
  const combined = [
    ...vocab.map((v) => ({ key: `v:${v.word}`, freq: v.frequency })),
    ...verbs.map((verb) => ({ key: `verb:${verb.infinitive}`, freq: verb.true_frequency })),
  ];
  combined.sort((a, b) => b.freq - a.freq);
  const rankOf = new Map();
  combined.forEach((entry, i) => rankOf.set(entry.key, i));
  return rankOf;
}

export function buildItemBank(vocab, verbs, lang) {
  const items = [];
  const introRank = buildIntroRanks(vocab, verbs);

  vocab.forEach((v) => {
    items.push({
      id: `v:${v.word}`,
      type: "vocab",
      word: v.word,
      gloss: v.gloss,
      rank: introRank.get(`v:${v.word}`),
    });
  });

  verbs.forEach((verb) => {
    const verbRank = introRank.get(`verb:${verb.infinitive}`);
    // the verb's own meaning is a vocab item too
    items.push({
      id: `v:${verb.infinitive}`,
      type: "vocab",
      word: verb.display_infinitive,
      gloss: verb.gloss,
      rank: verbRank,
    });

    for (const tense of lang.tenses) {
      const forms = verb[tense.key];
      if (!forms) continue;
      for (let p = 0; p < 6; p++) {
        const expected = forms[p];
        if (!expected) continue;
        const altKey = `${verb.infinitive}:${tense.key}:${p}`;
        items.push({
          id: `c:${altKey}`,
          type: "conj",
          infinitive: verb.infinitive,
          displayInfinitive: verb.display_infinitive,
          gloss: verb.gloss,
          tenseKey: tense.key,
          tenseLabel: tense.label,
          personIdx: p,
          pronounLabel: pronounFor(tense, p, verb, lang),
          expected,
          alternates: ALTERNATES[altKey] || [],
          rank: verbRank,
        });
      }
    }
  });

  items.forEach((item) => {
    item.lessonIndex = lessonIndexForRank(item.rank);
  });

  return items;
}
