// Optional "reward image" on a correct vocab answer, via the Unsplash API.
// Entirely optional and degrades silently to no-op when UNSPLASH_ACCESS_KEY
// isn't configured (js/image-config.js) or a request fails for any reason
// (network, rate limit, no match) -- a missing/broken image reward should
// never block or disrupt the actual review flow.

import { UNSPLASH_ACCESS_KEY } from "./image-config.js";

export function isConfigured() {
  return Boolean(UNSPLASH_ACCESS_KEY);
}

// Small in-memory cache so re-reviewing the same word in one session
// doesn't spend another API call (the free tier is rate-limited to 50/hr).
const cache = new Map();

// Returns { url, photographerName, photographerUrl, photoUrl } or null.
// `query` should be an English keyword (Unsplash's search works much
// better on English than on French).
export async function fetchRewardImage(query) {
  if (!isConfigured() || !query) return null;
  if (cache.has(query)) return cache.get(query);

  try {
    const url = new URL("https://api.unsplash.com/photos/random");
    url.searchParams.set("query", query);
    url.searchParams.set("orientation", "squarish");
    url.searchParams.set("content_filter", "high");

    const res = await fetch(url, {
      headers: { Authorization: `Client-ID ${UNSPLASH_ACCESS_KEY}` },
    });
    if (!res.ok) {
      cache.set(query, null);
      return null;
    }
    const data = await res.json();
    // Unsplash API guidelines: link both the photographer and Unsplash
    // itself, with utm tracking params, whenever a photo is displayed.
    const utm = "utm_source=french_reactivation_trainer&utm_medium=referral";
    const result = {
      url: data.urls?.small,
      photographerName: data.user?.name || "Unsplash",
      photographerUrl: data.user?.links?.html ? `${data.user.links.html}?${utm}` : `https://unsplash.com?${utm}`,
      photoUrl: data.links?.html ? `${data.links.html}?${utm}` : `https://unsplash.com?${utm}`,
    };
    if (!result.url) {
      cache.set(query, null);
      return null;
    }
    cache.set(query, result);
    return result;
  } catch (e) {
    console.error("Unsplash reward image fetch failed", e);
    cache.set(query, null);
    return null;
  }
}
