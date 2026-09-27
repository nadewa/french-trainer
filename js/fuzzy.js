// Typo/accent-tolerant answer checking.
// Exact match -> correct. Close match -> caller must ask the user to self-confirm
// ("I knew this" vs "I didn't"), never silently auto-accept. Far match -> wrong.

export function normalize(s) {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // strip combining accents
    .toLowerCase()
    .replace(/[’]/g, "'")
    .replace(/[^a-z0-9' -]/g, "")
    .trim()
    .replace(/\s+/g, " ");
}

export function levenshtein(a, b) {
  const m = a.length, n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;
  let prev = new Array(n + 1);
  let curr = new Array(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;
  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(
        prev[j] + 1,
        curr[j - 1] + 1,
        prev[j - 1] + cost
      );
    }
    [prev, curr] = [curr, prev];
  }
  return prev[n];
}

function closeThreshold(len) {
  if (len <= 3) return 1;
  if (len <= 7) return 2;
  return 3;
}

// Compare a typed answer against one or more acceptable target strings.
// Returns the best (closest) result across all targets.
export function checkAnswer(typed, targets) {
  const list = Array.isArray(targets) ? targets : [targets];
  const rawTyped = typed.trim().toLowerCase();

  let best = { verdict: "wrong", distance: Infinity, target: list[0] || "" };

  for (const target of list) {
    if (!target) continue;
    const rawTarget = target.trim().toLowerCase();
    if (rawTyped === rawTarget) {
      return { verdict: "exact", distance: 0, target };
    }
    const nTyped = normalize(typed);
    const nTarget = normalize(target);
    if (nTyped === nTarget) {
      // identical once accents are stripped -- still not exact, must self-confirm
      if (0 < best.distance) best = { verdict: "close", distance: 0.5, target };
      continue;
    }
    const dist = levenshtein(nTyped, nTarget);
    const threshold = closeThreshold(nTarget.length);
    if (dist <= threshold && dist < best.distance) {
      best = { verdict: "close", distance: dist, target };
    } else if (best.verdict === "wrong" && dist < best.distance) {
      best = { verdict: "wrong", distance: dist, target };
    }
  }
  return best;
}
