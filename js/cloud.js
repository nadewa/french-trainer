// Optional cloud sync via Supabase. Everything here degrades gracefully to
// no-ops when supabase-config.js still has its placeholder values -- the app
// is fully functional offline without ever touching this file's exports.

import { SUPABASE_URL, SUPABASE_ANON_KEY } from "./supabase-config.js";

let client = null;

export function isConfigured() {
  return Boolean(SUPABASE_URL) && Boolean(SUPABASE_ANON_KEY) && !SUPABASE_URL.startsWith("YOUR_");
}

function getClient() {
  if (!isConfigured()) return null;
  if (!client) {
    if (!window.supabase) {
      throw new Error("Supabase JS library did not load (check the <script> tag in index.html).");
    }
    client = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }
  return client;
}

export async function signUp(email, password) {
  const c = getClient();
  const { data, error } = await c.auth.signUp({ email, password });
  if (error) throw error;
  return data;
}

export async function signIn(email, password) {
  const c = getClient();
  const { data, error } = await c.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

export async function signOut() {
  const c = getClient();
  if (!c) return;
  await c.auth.signOut();
}

export async function getSession() {
  const c = getClient();
  if (!c) return null;
  const { data } = await c.auth.getSession();
  return data.session;
}

export function onAuthChange(cb) {
  const c = getClient();
  if (!c) return;
  c.auth.onAuthStateChange((_event, session) => cb(session));
}

// One row per user, holding the entire app state as JSON. Simple last-write-
// wins sync: no cross-device merge, whichever device pushed most recently
// wins. Fine for a single person's own devices, not a shared account.
export async function pullProgress(userId) {
  const c = getClient();
  const { data, error } = await c
    .from("progress")
    .select("state")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw error;
  return data ? data.state : null;
}

export async function pushProgress(userId, state) {
  const c = getClient();
  const { error } = await c
    .from("progress")
    .upsert({ user_id: userId, state, updated_at: new Date().toISOString() });
  if (error) throw error;
}
