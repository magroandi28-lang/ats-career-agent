"use client";

import { useRouter } from "next/navigation";
import { createClient } from "../lib/supabase/client";

export default function AuthMenu() {
  const router = useRouter();

  async function kijelentkezes() {
    await createClient().auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={kijelentkezes}
      className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
    >
      Kijelentkezés
    </button>
  );
}
