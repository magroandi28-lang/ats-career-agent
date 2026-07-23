"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "../../lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [jelszo, setJelszo] = useState("");
  const [hiba, setHiba] = useState("");
  const [uzenet, setUzenet] = useState("");
  const [dolgozik, setDolgozik] = useState(false);

  async function hitelesites(mod) {
    if (mod === "regisztracio" && jelszo.length < 12) {
      setHiba("Az új jelszó legalább 12 karakter legyen.");
      return;
    }
    setDolgozik(true);
    setHiba("");
    setUzenet("");
    const supabase = createClient();

    const eredmeny =
      mod === "belepes"
        ? await supabase.auth.signInWithPassword({ email, password: jelszo })
        : await supabase.auth.signUp({
            email,
            password: jelszo,
            options: {
              emailRedirectTo: `${window.location.origin}/auth/confirm`,
            },
          });

    if (eredmeny.error) {
      setHiba(
        mod === "belepes"
          ? "A belépés nem sikerült. Ellenőrizd az adatokat."
          : "A regisztráció nem sikerült.",
      );
    } else if (eredmeny.data.session) {
      const kovetkezo = new URLSearchParams(window.location.search).get("next");
      router.replace(
        kovetkezo?.startsWith("/") && !kovetkezo.startsWith("//")
          ? kovetkezo
          : "/",
      );
      router.refresh();
    } else {
      setUzenet("Nézd meg az emailedet a regisztráció megerősítéséhez.");
    }
    setDolgozik(false);
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          hitelesites("belepes");
        }}
        className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"
      >
        <h1 className="text-2xl font-semibold">Karrier-Ügynökség</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Lépj be, hogy a karrieradataid védve maradjanak.
        </p>

        <label className="mt-6 block text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          maxLength={320}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2"
        />

        <label className="mt-4 block text-sm font-medium" htmlFor="password">
          Jelszó
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          minLength={1}
          maxLength={128}
          value={jelszo}
          onChange={(event) => setJelszo(event.target.value)}
          className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2"
        />

        {hiba && <p className="mt-4 text-sm text-red-700">{hiba}</p>}
        {uzenet && <p className="mt-4 text-sm text-emerald-700">{uzenet}</p>}

        <button
          type="submit"
          disabled={dolgozik}
          className="mt-6 w-full rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Belépés
        </button>
        <button
          type="button"
          disabled={dolgozik}
          onClick={() => hitelesites("regisztracio")}
          className="mt-2 w-full rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium"
        >
          Új fiók létrehozása
        </button>
      </form>
    </main>
  );
}
