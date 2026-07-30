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
    // A félbehagyott folyamat nyomai a böngészőben maradnának, és a következő
    // belépő felhasználó örökölné őket ugyanezen a gépen.
    window.localStorage.removeItem("career_pending_start");
    window.localStorage.removeItem("career_pending_cv_import");
    window.localStorage.removeItem("career_pending_message");
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
        className="button-link rounded-full border px-4 py-2 text-xs font-semibold"
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
