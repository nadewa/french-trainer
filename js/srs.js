// Minimal SM-2 (SuperMemo 2) spaced-repetition scheduler.
// quality: 0-5 (we only ever produce 1, 2, 4, or 5 -- see app.js grading map)

const DAY_MS = 24 * 60 * 60 * 1000;

export function newCard() {
  return {
    repetitions: 0,
    interval: 0,
    ease: 2.5,
    due: Date.now(),
    lastQuality: null,
    seen: 0,
  };
}

export function schedule(card, quality, now = Date.now()) {
  const c = { ...card };
  c.seen += 1;
  c.lastQuality = quality;

  if (quality < 3) {
    c.repetitions = 0;
    c.interval = 1;
  } else {
    if (c.repetitions === 0) {
      c.interval = 1;
    } else if (c.repetitions === 1) {
      c.interval = 6;
    } else {
      c.interval = Math.round(c.interval * c.ease);
    }
    c.repetitions += 1;
  }

  c.ease = Math.max(
    1.3,
    c.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
  );

  c.due = now + c.interval * DAY_MS;
  return c;
}

export function isDue(card, now = Date.now()) {
  return card.due <= now;
}
