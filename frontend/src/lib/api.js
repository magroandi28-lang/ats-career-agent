"use client";

import { createClient } from "./supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");

export async function apiFetch(path, options = {}) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    window.location.assign("/login");
    throw new Error("Bejelentkezés szükséges.");
  }

  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401) {
    await supabase.auth.signOut();
    window.location.assign("/login");
  }
  return response;
}
