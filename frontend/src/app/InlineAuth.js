"use client";

import { useState } from "react";
import { createClient } from "../lib/supabase/client";

export default function InlineAuth() {
  const [mod, setMod] = useState("belepes");
  const [email, setEmail] = useState("");
  const [jelszo, setJelszo] = useState("");
  const [jelszoLathato, setJelszoLathato] = useState(false);
  const [hiba, setHiba] = useState("");
  const [uzenet, setUzenet] = useState("");
  const [dolgozik, setDolgozik] = useState(false);

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
                  "/",
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
        setUzenet("Sikeres belépés. A CV-folyamat folytatódik.");
      } else {
        setUzenet(
          "Elküldtük a megerősítő levelet. A link megnyitása után ugyanitt folytathatod.",
        );
      }
    } catch {
      setHiba("A szolgáltatás most nem érhető el. Próbáld újra néhány perc múlva.");
    } finally {
      setDolgozik(false);
    }
  }

  return (
    <div className="mt-7 max-w-xl">
      <div className="mb-5 grid grid-cols-2 rounded-xl border border-white/10 bg-black/20 p-1">
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
          htmlFor="flow-auth-email"
        >
          Email
        </label>
        <input
          id="flow-auth-email"
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
          htmlFor="flow-auth-password"
        >
          Jelszó
        </label>
        <div className="relative mt-2">
          <input
            id="flow-auth-password"
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
              ? "Belépés és folytatás"
              : "Fiók létrehozása"}
        </button>
      </form>
    </div>
  );
}
