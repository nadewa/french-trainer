// Groups vocab words and verbs into fixed-size "lessons" in frequency-introduction
// order, for the lesson-intro screen ("today we're learning...").

export const LESSON_SIZE = 10;

export function lessonIndexForRank(rank) {
  return Math.floor(rank / LESSON_SIZE);
}

// A "concept" is one headline thing being taught (a vocab word, or a verb --
// whose conjugation drills all belong to the same lesson as its meaning card).
export function buildConcepts(vocab, verbs, introRank) {
  const concepts = [];

  vocab.forEach((v) => {
    concepts.push({
      key: `v:${v.word}`,
      kind: "vocab",
      word: v.word,
      gloss: v.gloss,
      rank: introRank.get(`v:${v.word}`),
    });
  });

  verbs.forEach((verb) => {
    concepts.push({
      key: `verb:${verb.infinitive}`,
      kind: "verb",
      infinitive: verb.infinitive,
      displayInfinitive: verb.display_infinitive,
      gloss: verb.gloss,
      rank: introRank.get(`verb:${verb.infinitive}`),
    });
  });

  concepts.sort((a, b) => a.rank - b.rank);
  concepts.forEach((c) => {
    c.lessonIndex = lessonIndexForRank(c.rank);
  });
  return concepts;
}

export function groupByLesson(concepts) {
  const lessons = [];
  for (const c of concepts) {
    if (!lessons[c.lessonIndex]) lessons[c.lessonIndex] = [];
    lessons[c.lessonIndex].push(c);
  }
  return lessons;
}
