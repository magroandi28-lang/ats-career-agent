"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "../../lib/supabase/client";

// Az adatkezelési tájékoztató aktuális változata. Ha a tájékoztató
// érdemben változik, ezt is emelni kell, és a meglévő felhasználóktól
// újra be kell kérni a hozzájárulást.
const ADATKEZELES_VERZIO = "2026-07-26";

// Ugyanaz a pipa két helyen: regisztrációkor az űrlap alján, belépéskor
// közvetlenül a Google-gomb fölött. Egyszerre mindig csak az egyik látszik,
// és mindkettő ugyanazt az `elfogadva` állapotot állítja.
function HozzajarulasPipa({ elfogadva, setElfogadva, className }) {
  return (
    <label
      className={`flex cursor-pointer items-start gap-2.5 text-xs leading-5 text-slate-300 ${className}`}
    >
      <input
        type="checkbox"
        checked={elfogadva}
        onChange={(event) => setElfogadva(event.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 accent-amber-300"
      />
      <span>
        Elolvastam és elfogadom az{" "}
        <Link
          href="/adatkezeles"
          target="_blank"
          className="font-semibold text-amber-200 underline hover:text-amber-100"
        >
          adatkezelési tájékoztatót
        </Link>
        . Tudomásul veszem, hogy a CV-m és a Flow-val folytatott beszélgetésem a
        válasz elkészítéséhez a Google Gemini szolgáltatásába kerül.
      </span>
    </label>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [mod, setMod] = useState("belepes");
  const [keresztnev, setKeresztnev] = useState("");
  const [elfogadva, setElfogadva] = useState(false);
  const [megerositesreVar, setMegerositesreVar] = useState(false);

  // A `?mod=regisztracio` paraméterrel érkezőt rögtön a regisztrációs
  // űrlapon fogadjuk (Flow „Regisztráció" gombja így hivatkozik ide).
  // Szándékosan effektben és nem useSearchParams-szal: az utóbbi
  // Suspense-határt igényelne, ami nélkül a production build elhasal.
  useEffect(() => {
    const kert = new URLSearchParams(window.location.search).get("mod");
    if (kert === "regisztracio") setMod("regisztracio");
  }, []);
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

  async function googleBelepes() {
    // Hozzájárulás nélkül nem indulhat OAuth: a Supabase az ismeretlen
    // Google-fiókhoz azonnal létrehozza a fiókot, és onnantól nincs mit
    // visszavonni. A gomb is tiltva van, ez a második zár.
    if (!elfogadva) return;

    setDolgozik(true);
    setHiba("");
    setUzenet("");
    // Az OAuth-átirányítás elhagyja az oldalt, és a `signInWithOAuth` -- a
    // `signUp`-pal ellentétben -- nem tud user-metaadatot átvinni. A
    // hozzájárulás nyomát ezért itt tesszük el, és a visszatérés után
    // menti a főoldal a profilba.
    window.localStorage.setItem(
      "career_pending_gdpr_consent",
      JSON.stringify({
        gdpr_consent_version: ADATKEZELES_VERZIO,
        gdpr_consent_at: new Date().toISOString(),
      }),
    );
    // A Google-átirányítás elhagyja az oldalt, és az űrlap mezői elvesznek.
    // Ha a felhasználó beírta a keresztnevét, azt megőrizzük, és visszatérés
    // után a profiljába mentjük -- különben hiába adta meg.
    if (keresztnev.trim()) {
      window.localStorage.setItem(
        "career_pending_given_name",
        keresztnev.trim(),
      );
    }
    const supabase = createClient();
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/confirm?next=${encodeURIComponent(
            kovetkezoOldal(),
          )}`,
        },
      });
      if (error) {
        setHiba("A Google-bejelentkezés most nem sikerült. Próbáld újra.");
        setDolgozik(false);
      }
      // Sikeres indításkor a böngésző elnavigál a Google oldalára --
      // nincs több teendő itt, a /auth/confirm útvonal veszi át onnantól.
    } catch {
      setHiba("A szolgáltatás most nem érhető el. Próbáld újra néhány perc múlva.");
      setDolgozik(false);
    }
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
                // Ugyanabba a mezőbe kerül, amit a Google-belépés is tölt,
                // így Flow-nak egyetlen névforrása van, nem kettő.
                data: {
                  given_name: keresztnev.trim(),
                  // A hozzájárulás nyoma: mikor és melyik szövegváltozatra
                  // adta. Verzióváltáskor újra be kell kérni.
                  gdpr_consent_version: ADATKEZELES_VERZIO,
                  gdpr_consent_at: new Date().toISOString(),
                },
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
        // A megerősítő link a rendszer alapértelmezett böngészőjében nyílik
        // meg, ami gyakran NEM ez az ablak (pl. inkognitóból regisztrálva).
        // Ilyenkor ez az ablak sosem lép be magától -- ezt ki kell mondani,
        // különben a felhasználó vár valamire, ami nem fog megtörténni.
        setUzenet(
          "Elküldtük a megerősítő levelet — nyisd meg, és kattints a benne " +
            "lévő linkre. A link a gépeden beállított alapértelmezett " +
            "böngészőben nyílik meg, és ott rögtön be is lépsz. Ha ez egy " +
            "másik ablak, ott folytasd — vagy jelentkezz be itt az imént " +
            "megadott jelszavaddal.",
        );
        setMegerositesreVar(true);
      }
    } catch {
      setHiba("A szolgáltatás most nem érhető el. Próbáld újra néhány perc múlva.");
    } finally {
      setDolgozik(false);
    }
  }

  return (
    <main className="career-shell career-grid min-h-screen px-4 py-8 sm:py-12">
      <div className="mx-auto w-full max-w-2xl">
        <Link
          href="/"
          className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.035] px-4 py-2 text-xs font-semibold text-slate-300 hover:border-amber-300/35 hover:text-amber-100"
        >
          ← Vissza a kezdőoldalra
        </Link>

        <section className="overflow-hidden rounded-3xl border border-white/8 bg-[#0b1220]">
          <div className="grid grid-cols-1 sm:grid-cols-[42%_1fr]">
            <div className="flex flex-col justify-center border-b border-white/8 bg-white/[0.02] px-7 py-9 sm:border-b-0 sm:border-r">
              <div className="flow-pulse mb-4 grid h-11 w-11 place-items-center rounded-full border border-amber-300/45 bg-amber-300/10">
                <span className="gold-text font-serif text-lg font-bold">K</span>
              </div>
              <p className="whitespace-nowrap font-serif text-lg font-semibold text-white">
                Karrier-Ügynökség
              </p>
              <p className="mb-6 mt-1.5 text-[9.5px] uppercase tracking-[0.1em] text-slate-500">
                Biztonságos személyes munkatér
              </p>

              <h1 className="text-xl font-semibold text-white">
                {mod === "belepes" ? "Üdv újra!" : "Hozd létre a fiókodat"}
              </h1>
              <div
                className="my-3.5 h-0.5 w-[52px] bg-gradient-to-r from-amber-200 to-[#b08d57]"
                style={{ boxShadow: "0 0 12px rgba(176,141,87,0.5)" }}
              />
              <p className="text-[13px] leading-relaxed text-slate-400">
                {mod === "belepes"
                  ? "Folytasd onnan a karrierutadat, ahol abbahagytad."
                  : "A fiók védi és több eszközön elérhetővé teszi a karrieradataidat."}
              </p>
            </div>

            <div className="px-7 py-9 sm:px-9">
              {/* Belépés módban ez az egyetlen út, amin új fiók keletkezhet
                  (ismeretlen Google-fiókhoz a Supabase azonnal létrehozza),
                  ezért itt a pipának a gomb mellett a helye. Regisztráció
                  módban az űrlap alján lévő példány takarja le. */}
              {mod === "belepes" && (
                <HozzajarulasPipa
                  elfogadva={elfogadva}
                  setElfogadva={setElfogadva}
                  className="mb-4"
                />
              )}

              <button
                type="button"
                onClick={googleBelepes}
                disabled={dolgozik || !elfogadva}
                className="mb-5 flex w-full items-center justify-center gap-3 rounded-xl border border-white/15 bg-white/[0.04] px-4 py-3.5 text-sm font-semibold text-slate-100 hover:border-amber-300/40 hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                  <path
                    fill="#4285F4"
                    d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.88 2.7-6.62z"
                  />
                  <path
                    fill="#34A853"
                    d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.81.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z"
                  />
                  <path
                    fill="#EA4335"
                    d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z"
                  />
                </svg>
                Folytatás Google-lal
              </button>

              <div className="mb-5 flex items-center gap-3">
                <span className="h-px flex-1 bg-white/10" />
                <span className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  vagy
                </span>
                <span className="h-px flex-1 bg-white/10" />
              </div>

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  hitelesites();
                }}
              >
                {mod === "regisztracio" && (
                  <div className="mb-3">
                    <label
                      className="block text-xs font-semibold text-slate-300"
                      htmlFor="keresztnev"
                    >
                      Keresztneved
                    </label>
                    <input
                      id="keresztnev"
                      type="text"
                      /* A böngésző „keresztnév" bejegyzése gyakran a
                         vezetéknevet tartalmazza, és így rossz néven
                         szólítanánk a felhasználót. Ne találgasson. */
                      autoComplete="off"
                      required
                      maxLength={80}
                      value={keresztnev}
                      onChange={(event) => setKeresztnev(event.target.value)}
                      placeholder="Andrea"
                      className="mt-2 w-full rounded-xl border border-white/12 bg-slate-950/55 px-3.5 py-3 text-sm text-white placeholder:text-slate-600 focus:border-amber-300/50"
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
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
                      className="mt-2 w-full rounded-xl border border-white/12 bg-slate-950/55 px-3.5 py-3 text-sm text-white placeholder:text-slate-600 focus:border-amber-300/50"
                    />
                  </div>

                  <div>
                    <label
                      className="block text-xs font-semibold text-slate-300"
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
                        className="w-full rounded-xl border border-white/12 bg-slate-950/55 px-3.5 py-3 pr-16 text-sm text-white focus:border-amber-300/50"
                      />
                      <button
                        type="button"
                        onClick={() => setJelszoLathato((elozo) => !elozo)}
                        className="absolute inset-y-0 right-2.5 text-[11px] font-semibold text-slate-500 hover:text-amber-200"
                      >
                        {jelszoLathato ? "Elrejtés" : "Mutatás"}
                      </button>
                    </div>
                  </div>
                </div>

                {mod === "regisztracio" && (
                  <>
                    <p className="mt-2 text-xs text-slate-500">
                      Legalább 12 karakter. Soha ne használd másik fiókod jelszavát.
                    </p>

                    <HozzajarulasPipa
                      elfogadva={elfogadva}
                      setElfogadva={setElfogadva}
                      className="mt-4"
                    />
                  </>
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
                    className="mt-4 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.07] px-4 py-3 text-sm leading-6 text-emerald-100"
                  >
                    {uzenet}
                  </p>
                )}
                {megerositesreVar && (
                  <button
                    type="button"
                    onClick={() => {
                      setMegerositesreVar(false);
                      setUzenet("");
                      setHiba("");
                      setMod("belepes");
                    }}
                    className="mt-3 w-full rounded-xl border border-amber-300/40 px-4 py-3 text-sm font-semibold text-amber-100 hover:border-amber-200 hover:bg-amber-300/10"
                  >
                    Belépés ebben az ablakban
                  </button>
                )}

                <button
                  type="submit"
                  disabled={dolgozik || (mod === "regisztracio" && !elfogadva)}
                  className="mt-6 w-full rounded-xl bg-[#b08d57] px-4 py-[15px] text-sm font-bold text-[#1e1206] hover:bg-[#c29c63] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {dolgozik
                    ? "Egy pillanat…"
                    : mod === "belepes"
                      ? "Belépés"
                      : "Fiók létrehozása"}
                </button>
              </form>

              <button
                type="button"
                onClick={() =>
                  modValtas(mod === "belepes" ? "regisztracio" : "belepes")
                }
                className="mt-4 w-full rounded-xl border border-[#b08d57]/40 bg-[#b08d57]/[0.06] px-4 py-3 text-center text-sm font-semibold text-amber-200/90 hover:border-[#b08d57]/70 hover:bg-[#b08d57]/[0.12]"
              >
                {mod === "belepes"
                  ? "Nincs még fiókod? Regisztrálj itt →"
                  : "Van már fiókod? Jelentkezz be →"}
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

