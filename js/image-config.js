// Fill this in to turn on the "reward image" shown on a correct vocabulary
// answer -- see README.md "Image reward setup" for the exact steps. Until
// you do, the app works exactly as before, just without the reward image.
//
// Unlike the Supabase anon key, this one is a real (if low-stakes) trade-off
// to expose client-side: it's a request key, not a secret protected by
// server-side row-level rules, so anyone who opens devtools can read it out
// of a network request and make requests against your quota. Unsplash's
// free "Demo" tier (50 requests/hour) is meant for exactly this kind of
// client-side hobby use, so the real-world downside is small -- worst case,
// someone else exhausts your hourly quota and images stop appearing until
// it resets, not a billing or security incident. If that's not an
// acceptable trade-off for you, leave this blank; the app degrades
// gracefully (no image, no error) with no key configured.
export const UNSPLASH_ACCESS_KEY = "";
