"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "../../lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [mod, setMod] = useState("belepes");
  const [email, setEmail] = useState("");
  const [jelszo, setJelszo] = useState("");
  const [jelszoLathato, setJelszoLathato] = useState(false);
  const [hiba, setHiba] = useState("");
  const [uzenet, setUzenet] = useState("");
  const [dolgozik, setDolgozik] = useState(false);

  function kovetkezoOldal() {
    const kovetkezo = new URLSearchParams(window.location.search).get("next");
    return kovetkezo?.startsWith("/") && !kovetkezo.startsWith("//")
      ? kovetkezo
      : "/";
  }

  function modValtas(ujMod) {
    setMod(ujMod);
    setHiba("");
    setUzenet("");
  }

  async function hitelesites() {
    if (mod === "regisztracio" && jelszo.length < 12) {
      setHiba("Az új jelszó legalább 12 karakter legyen.");
      return;
    }

    setDolgozik(true);
    setHiba("");
    setUzenet("");
    const supabase = createClient();

    try {
      const eredmeny =
        mod === "belepes"
          ? await supabase.auth.signInWithPassword({
              email: email.trim(),
              password: jelszo,
            })
          : await supabase.auth.signUp({
              email: email.trim(),
              password: jelszo,
              options: {
                emailRedirectTo: `${window.location.origin}/auth/confirm?next=${encodeURIComponent(
                  kovetkezoOldal(),
                )}`,
              },
            });

      if (eredmeny.error) {
        setHiba(
          mod === "belepes"
            ? "A belépés nem sikerült. Ellenőrizd az emailcímet és a jelszót."
            : `A regisztráció nem sikerült: ${eredmeny.error.message}`,
        );
      } else if (eredmeny.data.session) {
        router.replace(kovetkezoOldal());
        router.refresh();
      } else {
        setUzenet(
          "Elküldtük a megerősítő levelet. Nyisd meg az emailedet, majd kattints a benne lévő linkre.",
        );
      }
    } catch {
      setHiba("A szolgáltatás most nem érhető el. Próbáld újra néhány perc múlva.");
    } finally {
      setDolgozik(false);
    }
  }

  return (
    <main className="career-shell career-grid min-h-screen px-4 py-8 sm:py-12">
      <div className="mx-auto w-full max-w-md">
        <Link
          href="/"
          className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.035] px-4 py-2 text-xs font-semibold text-slate-300 hover:border-amber-300/35 hover:text-amber-100"
        >
          ← Vissza a kezdőoldalra
        </Link>

        <section className="glass-panel overflow-hidden rounded-3xl">
          <div className="border-b border-white/8 px-6 py-6 sm:px-8">
            <div className="mb-5 flex items-center gap-3">
              <div className="flow-pulse grid h-11 w-11 place-items-center rounded-full border border-amber-300/45 bg-amber-300/10">
                <span className="gold-text font-serif text-lg font-bold">K</span>
              </div>
              <div>
                <p className="font-serif text-xl font-semibold text-white">
                  Karrier-Ügynökség
                </p>
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
                  Biztonságos személyes munkatér
                </p>
              </div>
            </div>

            <h1 className="text-2xl font-semibold text-white">
              {mod === "belepes" ? "Üdv újra!" : "Hozd létre a fiókodat"}
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              {mod === "belepes"
                ? "Folytasd onnan a karrierutadat, ahol abbahagytad."
                : "A fiók védi és több eszközön elérhetővé teszi a karrieradataidat."}
            </p>
          </div>

          <div className="p-6 sm:p-8">
            <div className="mb-6 grid grid-cols-2 rounded-xl border border-white/10 bg-black/20 p-1">
              {[
                ["belepes", "Belépés"],
                ["regisztracio", "Regisztráció"],
              ].map(([ertek, felirat]) => (
                <button
                  key={ertek}
                  type="button"
                  onClick={() => modValtas(ertek)}
                  className={`rounded-lg px-3 py-2.5 text-sm font-semibold ${
                    mod === ertek
                      ? "bg-amber-300 text-slate-950"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {felirat}
                </button>
              ))}
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                hitelesites();
              }}
            >
              <label
                className="block text-xs font-semibold text-slate-300"
                htmlFor="email"
              >
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
                placeholder="nev@email.hu"
                className="mt-2 w-full rounded-xl border border-white/12 bg-slate-950/55 px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:border-amber-300/50"
              />

              <label
                className="mt-5 block text-xs font-semibold text-slate-300"
                htmlFor="password"
              >
                Jelszó
              </label>
              <div className="relative mt-2">
                <input
                  id="password"
                  type={jelszoLathato ? "text" : "password"}
                  autoComplete={
                    mod === "belepes" ? "current-password" : "new-password"
                  }
                  required
                  minLength={mod === "regisztracio" ? 12 : 1}
                  maxLength={128}
                  value={jelszo}
                  onChange={(event) => setJelszo(event.target.value)}
                  className="w-full rounded-xl border border-white/12 bg-slate-950/55 px-4 py-3 pr-20 text-sm text-white focus:border-amber-300/50"
                />
                <button
                  type="button"
                  onClick={() => setJelszoLathato((elozo) => !elozo)}
                  className="absolute inset-y-0 right-3 text-xs font-semibold text-slate-500 hover:text-amber-200"
                >
                  {jelszoLathato ? "Elrejtés" : "Mutatás"}
                </button>
              </div>

              {mod === "regisztracio" && (
                <p className="mt-2 text-xs text-slate-500">
                  Legalább 12 karakter. Soha ne használd másik fiókod jelszavát.
                </p>
              )}

              {hiba && (
                <p
                  role="alert"
                  className="mt-4 rounded-xl border border-red-300/20 bg-red-300/[0.07] px-4 py-3 text-sm text-red-100"
                >
                  {hiba}
                </p>
              )}
              {uzenet && (
                <p
                  role="status"
                  className="mt-4 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.07] px-4 py-3 text-sm text-emerald-100"
                >
                  {uzenet}
                </p>
              )}

              <button
                type="submit"
                disabled={dolgozik}
                className="mt-6 w-full rounded-xl bg-amber-300 px-4 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {dolgozik
                  ? "Egy pillanat…"
                  : mod === "belepes"
                    ? "Belépés"
                    : "Fiók létrehozása"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}

