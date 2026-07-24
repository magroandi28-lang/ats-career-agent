"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AuthMenu from "./AuthMenu";
import KarrierUgynok from "./KarrierUgynok";
import { apiFetch } from "../lib/api";
import { createClient } from "../lib/supabase/client";

const KEZDO_LEPESEK = [
  {
    id: "cv",
    cim: "Van CV-m",
    leiras: "Átnézzük, pontosítjuk a profilod, és csak utána keresünk.",
  },
  {
    id: "nincs-cv",
    cim: "Nincs CV-m",
    leiras: "Rövid interjúból építünk ellenőrizhető karrierprofilt.",
  },
  {
    id: "valt",
    cim: "Pályát váltanék",
    leiras: "Reális átjárókat, készséghiányt és képzési utat keresünk.",
  },
];

const MODULOK = [
  { nev: "Piaci körkép", jel: "01", allapot: "adatkapcsolat következik" },
  { nev: "Álláslehetőségek", jel: "02", allapot: "adatkapcsolat következik" },
  { nev: "Képzések", jel: "03", allapot: "adatkapcsolat következik" },
  { nev: "Külföld", jel: "04", allapot: "adatkapcsolat következik" },
  { nev: "Portfólió Stúdió", jel: "05", allapot: "tervezés alatt" },
];

const GPS_LEPESEK = [
  { nev: "Kiindulópont", allapot: "aktiv" },
  { nev: "Karrierprofil", allapot: "zart" },
  { nev: "Cél és irány", allapot: "zart" },
  { nev: "Piaci illeszkedés", allapot: "zart" },
  { nev: "Pályázati csomag", allapot: "zart" },
];

function belepesUrl(kovetkezo = "/") {
  return `/login?next=${encodeURIComponent(kovetkezo)}`;
}

export default function Home() {
  const [session, setSession] = useState(undefined);
  const [uzenetek, setUzenetek] = useState([
    {
      szerep: "flow",
      szoveg:
        "Szia, Flow vagyok. Először megértem, honnan indulsz, aztán mindig csak a következő értelmes lépést mutatom.",
    },
  ]);
  const [szoveg, setSzoveg] = useState("");
  const [kuldesFolyamatban, setKuldesFolyamatban] = useState(false);
  const [hiba, setHiba] = useState(null);
  const [karrierSzakma, setKarrierSzakma] = useState(null);
  const [gpsNyitva, setGpsNyitva] = useState(false);
  const belepve = Boolean(session);

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

  const gpsStatusz = useMemo(
    () => (belepve ? "Profilindításra kész" : "Vendég mód"),
    [belepve],
  );

  function belepesKeres(uzenet) {
    setUzenetek((elozo) => [
      ...elozo,
      { szerep: "user", szoveg: uzenet },
      {
        szerep: "flow",
        szoveg:
          "Ehhez személyes adatokkal dolgozunk, ezért itt kérek belépést. A nyilvános felületet továbbra is használhatod fiók nélkül.",
        belepes: true,
      },
    ]);
  }

  async function uzenetKuldese(uzenetSzoveg) {
    const tiszta = uzenetSzoveg.trim();
    if (!tiszta || kuldesFolyamatban) return;

    if (!belepve) {
      setSzoveg("");
      belepesKeres(tiszta);
      return;
    }

    setHiba(null);
    setUzenetek((elozo) => [...elozo, { szerep: "user", szoveg: tiszta }]);
    setSzoveg("");
    setKuldesFolyamatban(true);

    try {
      // A backend saját maga tárolja és olvassa vissza az előzményt
      // (private.flow_messages) -- nem küldünk elozmenyek mezőt, nem
      // bízunk a kliens állítására.
      const valasz = await apiFetch("/api/v1/flow/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kerdes: tiszta,
          profil: {},
          app_ismeret:
            "A Karrier-Ügynökség ellenőrzött karrierprofilt, Career GPS-t, " +
            "piaci körképet, állásillesztést és pályázati anyagokat készít.",
        }),
      });
      if (!valasz.ok) throw new Error(`flow-messages: ${valasz.status}`);
      const dontes = await valasz.json();

      setUzenetek((elozo) => [
        ...elozo,
        { szerep: "flow", szoveg: dontes.response_message || "" },
      ]);

      // Strukturált döntés (FlowDecision) -- nincs kliensoldali regex,
      // a proposed_action/szakma mező közvetlenül a backend válasza.
      if (dontes.proposed_action === "karrier_ugynok_inditasa" && dontes.szakma) {
        setKarrierSzakma(dontes.szakma);
      }
    } catch {
      setHiba(
        "Flow most nem érte el a háttérrendszert. Az üzeneted megmaradt, próbáld újra később.",
      );
    } finally {
      setKuldesFolyamatban(false);
    }
  }

  const gpsPanel = (
    <aside className="glass-panel rounded-3xl p-5 lg:sticky lg:top-6 lg:p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-300/75">
            Élő útiterv
          </p>
          <h2 className="text-xl font-semibold text-white">Career GPS</h2>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300">
          {gpsStatusz}
        </span>
      </div>

      <div className="mb-6 rounded-2xl border border-amber-300/15 bg-amber-300/[0.04] p-4">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="text-slate-300">Karrierút készültsége</span>
          <span className="font-semibold text-amber-200">0%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
          <div className="h-full w-[4%] rounded-full bg-gradient-to-r from-amber-500 to-amber-200" />
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">
          Nem becsülünk találomra. A sáv csak ellenőrzött lépések után halad.
        </p>
      </div>

      <ol className="space-y-1">
        {GPS_LEPESEK.map((lepes, index) => (
          <li key={lepes.nev} className="relative flex gap-3 pb-4">
            {index < GPS_LEPESEK.length - 1 && (
              <span className="absolute left-[13px] top-7 h-[calc(100%_-_18px)] w-px bg-white/10" />
            )}
            <span
              className={`relative z-10 mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[10px] font-bold ${
                lepes.allapot === "aktiv"
                  ? "flow-pulse border-amber-300/60 bg-amber-300 text-slate-950"
                  : "border-white/12 bg-slate-950/70 text-slate-500"
              }`}
            >
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <p
                className={`text-sm font-medium ${
                  lepes.allapot === "aktiv" ? "text-amber-100" : "text-slate-400"
                }`}
              >
                {lepes.nev}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {lepes.allapot === "aktiv"
                  ? "Válassz egy kiindulási módot."
                  : "Az előző lépés után nyílik meg."}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-2 rounded-2xl border border-white/8 bg-black/15 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Következő lépés
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-200">
          {belepve
            ? "Mondd el Flow-nak, hogy van-e már CV-d."
            : "A személyes karrierút indításához jelentkezz be."}
        </p>
      </div>
    </aside>
  );

  return (
    <main className="career-shell career-grid min-h-screen">
      <header className="border-b border-white/8 bg-[#070b16]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1480px] items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flow-pulse grid h-10 w-10 place-items-center rounded-full border border-amber-300/45 bg-amber-300/10">
              <span className="gold-text font-serif text-lg font-bold">K</span>
            </div>
            <div>
              <p className="font-serif text-lg font-semibold text-white">
                Karrier-Ügynökség
              </p>
              <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">
                AI-asszisztált karrierfejlesztés
              </p>
            </div>
          </div>
          <AuthMenu />
        </div>
      </header>

      <div className="mx-auto max-w-[1480px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <section className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.3em] text-amber-300/70">
              Egy hely, ahol összeáll a következő lépés
            </p>
            <h1 className="font-serif text-3xl leading-tight text-white sm:text-4xl lg:text-5xl">
              Ne csak állást keress.
              <span className="gold-text ml-2 italic">Építs karrierutat.</span>
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400 sm:text-base">
              Flow megérti a helyzetedet, a Career GPS pedig láthatóvá teszi,
              mi készült el, mi hiányzik, és mi legyen a következő lépés.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setGpsNyitva((elozo) => !elozo)}
            className="rounded-full border border-amber-300/30 bg-amber-300/10 px-4 py-2 text-xs font-semibold text-amber-100 lg:hidden"
          >
            {gpsNyitva ? "Career GPS bezárása" : "Career GPS megnyitása"}
          </button>
        </section>

        {gpsNyitva && <div className="mb-6 lg:hidden">{gpsPanel}</div>}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.72fr)]">
          <section className="min-w-0">
            <div className="glass-panel overflow-hidden rounded-3xl">
              <div className="flex items-center justify-between gap-4 border-b border-white/8 px-5 py-4 sm:px-6">
                <div className="flex items-center gap-3">
                  <span className="flow-pulse h-2.5 w-2.5 rounded-full bg-amber-300" />
                  <div>
                    <h2 className="text-sm font-semibold text-white">Flow</h2>
                    <p className="text-[11px] text-slate-500">
                      Egyetlen kezelő, ellenőrzött következő lépések
                    </p>
                  </div>
                </div>
                <span className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-emerald-200/80">
                  elérhető
                </span>
              </div>

              <div className="min-h-[300px] space-y-4 p-5 sm:p-6">
                {uzenetek.map((uzenet, index) => (
                  <div
                    key={`${uzenet.szerep}-${index}`}
                    className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-6 sm:max-w-[82%] ${
                      uzenet.szerep === "flow"
                        ? "border border-amber-300/12 bg-amber-300/[0.05] text-slate-200"
                        : "ml-auto bg-slate-100 text-slate-950"
                    }`}
                  >
                    {uzenet.szoveg}
                    {uzenet.belepes && (
                      <Link
                        href={belepesUrl("/")}
                        className="mt-3 inline-flex rounded-full bg-amber-300 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-amber-200"
                      >
                        Belépés a személyes folytatáshoz
                      </Link>
                    )}
                  </div>
                ))}
                {kuldesFolyamatban && (
                  <div className="max-w-[82%] rounded-2xl border border-amber-300/12 bg-amber-300/[0.05] px-4 py-3 text-sm text-slate-400">
                    Flow feldolgozza a következő lépést…
                  </div>
                )}
              </div>

              {!karrierSzakma && (
                <div className="grid gap-3 border-t border-white/8 p-5 sm:grid-cols-3 sm:p-6">
                  {KEZDO_LEPESEK.map((lepes) => (
                    <button
                      key={lepes.id}
                      type="button"
                      onClick={() => uzenetKuldese(lepes.cim)}
                      disabled={kuldesFolyamatban}
                      className="group rounded-2xl border border-white/10 bg-white/[0.025] p-4 text-left hover:-translate-y-0.5 hover:border-amber-300/35 hover:bg-amber-300/[0.05] disabled:opacity-50"
                    >
                      <span className="text-sm font-semibold text-slate-100 group-hover:text-amber-100">
                        {lepes.cim}
                      </span>
                      <span className="mt-2 block text-xs leading-5 text-slate-500">
                        {lepes.leiras}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  uzenetKuldese(szoveg);
                }}
                className="flex gap-2 border-t border-white/8 bg-black/10 p-4 sm:p-5"
              >
                <input
                  value={szoveg}
                  onChange={(event) => setSzoveg(event.target.value)}
                  placeholder={
                    belepve
                      ? "Írd le, miben akadtál el…"
                      : "Kérdezz, vagy válassz egy kiindulópontot…"
                  }
                  className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:border-amber-300/45"
                />
                <button
                  type="submit"
                  disabled={kuldesFolyamatban || !szoveg.trim()}
                  className="rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Küldés
                </button>
              </form>
            </div>

            {hiba && (
              <div className="mt-4 rounded-2xl border border-red-300/20 bg-red-300/[0.06] px-4 py-3 text-sm text-red-100">
                {hiba}
              </div>
            )}

            {karrierSzakma && (
              <div className="glass-panel mt-6 rounded-3xl p-5 sm:p-6">
                <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-amber-200/70">
                  Flow elindította a keresést
                </p>
                <KarrierUgynok kezdoSzakma={karrierSzakma} />
              </div>
            )}

            <section className="mt-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-200">
                  A rendszer képességei
                </h2>
                <span className="text-[11px] text-slate-600">
                  Valós bekötési állapot
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {MODULOK.map((modul) => (
                  <article
                    key={modul.nev}
                    className="rounded-2xl border border-white/8 bg-white/[0.025] p-4"
                  >
                    <span className="text-[10px] font-bold tracking-[0.2em] text-amber-300/60">
                      {modul.jel}
                    </span>
                    <h3 className="mt-3 text-sm font-semibold text-slate-200">
                      {modul.nev}
                    </h3>
                    <p className="mt-2 text-[11px] leading-4 text-slate-600">
                      {modul.allapot}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </section>

          <div className="hidden lg:block">{gpsPanel}</div>
        </div>
      </div>
    </main>
  );
}
