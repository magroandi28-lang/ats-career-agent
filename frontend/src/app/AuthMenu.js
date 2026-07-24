"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "../lib/supabase/client";

export default function AuthMenu() {
  const router = useRouter();
  const [session, setSession] = useState(undefined);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => subscription.unsubscribe();
  }, []);

  async function kijelentkezes() {
    await createClient().auth.signOut();
    router.replace("/");
    router.refresh();
  }

  if (session === undefined) {
    return (
      <span
        aria-label="Munkamenet ellenőrzése"
        className="h-9 w-24 animate-pulse rounded-full bg-white/5"
      />
    );
  }

  if (!session) {
    return (
      <Link
        href="/login?next=/"
        className="rounded-full border border-amber-300/40 bg-amber-300/10 px-4 py-2 text-xs font-semibold text-amber-100 hover:border-amber-200 hover:bg-amber-300/15"
      >
        Belépés
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={kijelentkezes}
      className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-semibold text-slate-200 hover:border-amber-300/40 hover:text-amber-100"
    >
      Kijelentkezés
    </button>
  );
}
