import { createClient, SupabaseClient } from "@supabase/supabase-js";

let _supabase: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (_supabase) return _supabase;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !key) {
    // Return a dummy client that won't crash at build time
    // Auth will simply not work until env vars are set
    _supabase = createClient("https://placeholder.supabase.co", "placeholder");
    return _supabase;
  }

  _supabase = createClient(url, key);
  return _supabase;
}

export const supabase = typeof window !== "undefined"
  ? getSupabase()
  : (null as unknown as SupabaseClient);
