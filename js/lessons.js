// Groups vocab words and verbs into fixed-size "lessons" in frequency-introduction
// order, for the lesson-intro screen ("today we're learning...").

export const LESSON_SIZE = 10;

export function lessonIndexForRank(rank) {
  return Math.floor(rank / LESSON_SIZE);
}

// A "level" is a coarser difficulty band on top of lessons: 10 lessons (100
// words/verbs, by frequency rank) per level, so level 1 = ranks 1-100, level
// 2 = 101-200, etc. Lessons already unlock in strict frequency order, so a
// word's level is simply which 100-word band its rank falls in -- no extra
// state to track, just a coarser view of the same progression.
export const LEVEL_SIZE = 10; // lessons per level

export function levelIndexForLesson(lessonIndex) {
  return Math.floor(lessonIndex / LEVEL_SIZE);
}

export function levelIndexForRank(rank) {
  return levelIndexForLesson(lessonIndexForRank(rank));
}

export function levelLabel(levelIndex) {
  const start = levelIndex * LEVEL_SIZE * LESSON_SIZE + 1;
  const end = (levelIndex + 1) * LEVEL_SIZE * LESSON_SIZE;
  return `Level ${levelIndex + 1} — words ${start}–${end}`;
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
