"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import AuthMenu from "./AuthMenu";
import ProfileGate from "./ProfileGate";
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

const CV_MUVELETEK = [
  {
    id: "ellenorzes",
    intent: "cv_ellenorzes",
    cim: "Csak vizsgáld át",
    leiras:
      "Hibák, érthetőség és ATS-kockázatok. A CV szövegét nem írjuk át.",
    kerdes: "A meglévő CV-met szeretném ellenőrizni, átírás nélkül.",
  },
  {
    id: "frissites",
    intent: "cv_frissites",
    cim: "Írd át és frissítsd",
    leiras:
      "A célmunkakör valós elvárásaihoz igazítjuk, de nem találunk ki tapasztalatot.",
    kerdes:
      "A meglévő CV-met szeretném frissíteni és átírni a célmunkaköröm elvárásai alapján.",
  },
  {
    id: "konkret",
    intent: "konkret_palyazas",
    cim: "Konkrét állásra szabás",
    leiras:
      "Már van egy hirdetésed. A link vagy a hirdetés szövege alapján készítjük el a célzott változatot.",
    kerdes:
      "Egy konkrét álláshirdetésre szeretném szabni a meglévő CV-met.",
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

const KEZDO_UZENET = {
  szerep: "flow",
  szoveg:
    "Szia, Flow vagyok. Először megértem, honnan indulsz, aztán mindig csak a következő értelmes lépést mutatom.",
};

function belepesUrl(kovetkezo = "/") {
  return `/login?next=${encodeURIComponent(kovetkezo)}`;
}

export default function Home() {
  const [session, setSession] = useState(undefined);
  const [uzenetek, setUzenetek] = useState([KEZDO_UZENET]);
  const [szoveg, setSzoveg] = useState("");
  const [kuldesFolyamatban, setKuldesFolyamatban] = useState(false);
  const [hiba, setHiba] = useState(null);
  const [workflowState, setWorkflowState] = useState(null);
  const [gpsNyitva, setGpsNyitva] = useState(false);
  const [kezdoValasztas, setKezdoValasztas] = useState(null);
  const [cvMuvelet, setCvMuvelet] = useState(null);
  const kezdoValasztasRef = useRef(null);
  const belepesKeresRef = useRef(false);
  const folytatasRef = useRef(false);
  const belepve = Boolean(session);
  const belepesFuggoben = !belepve && Boolean(kezdoValasztas);

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

  useEffect(() => {
    if (!session) return;
    apiFetch("/api/v1/profile")
      .then((response) => (response.ok ? response.json() : null))
      .then((profile) => {
        if (profile?.current_state) setWorkflowState(profile.current_state);
      })
      .catch(() => {});
  }, [session]);

  useEffect(() => {
    if (!session || folytatasRef.current) return;
    const fuggoben = window.localStorage.getItem("career_pending_start");
    if (fuggoben !== "cv") return;

    folytatasRef.current = true;
    window.localStorage.removeItem("career_pending_start");
    kezdoValasztasRef.current = "cv";
    belepesKeresRef.current = false;
    setKezdoValasztas("cv");
  }, [session]);

  const gpsStatusz = useMemo(
    () => (belepve ? "Profilindításra kész" : "Vendég mód"),
    [belepve],
  );

  function belepesKeres() {
    if (belepesKeresRef.current) return;
    belepesKeresRef.current = true;
  }

  function kezdoLepesValasztasa(lepes) {
    if (kezdoValasztasRef.current || kuldesFolyamatban) return;
    kezdoValasztasRef.current = lepes.id;
    setKezdoValasztas(lepes.id);
    if (lepes.id === "cv") {
      if (!belepve) {
        window.localStorage.setItem("career_pending_start", "cv");
        belepesKeres();
        return;
      }
      return;
    }
    uzenetKuldese(lepes.cim);
  }

  async function cvMuveletValasztasa(muvelet) {
    if (cvMuvelet || kuldesFolyamatban) return;
    setHiba(null);
    setKuldesFolyamatban(true);

    try {
      const valasz = await apiFetch("/api/v1/workflow/intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent: muvelet.intent }),
      });
      if (!valasz.ok) throw new Error(`workflow-intent: ${valasz.status}`);
      const dontes = await valasz.json();
      setCvMuvelet(muvelet.id);
      setWorkflowState(dontes.current_state);
    } catch {
      setHiba("A CV-művelet indítása nem sikerült. Próbáld újra.");
    } finally {
      setKuldesFolyamatban(false);
    }
  }

  function kezdoAllapotVisszaallitasa() {
    if (kuldesFolyamatban) return;
    window.localStorage.removeItem("career_pending_start");
    kezdoValasztasRef.current = null;
    belepesKeresRef.current = false;
    setKezdoValasztas(null);
    setCvMuvelet(null);
    setWorkflowState(null);
    setUzenetek([KEZDO_UZENET]);
    setSzoveg("");
    setHiba(null);
  }

  async function uzenetKuldese(uzenetSzoveg) {
    const tiszta = uzenetSzoveg.trim();
    if (!tiszta || kuldesFolyamatban) return;

    if (!belepve) {
      if (!kezdoValasztasRef.current) {
        kezdoValasztasRef.current = "szabad-szoveg";
        setKezdoValasztas("szabad-szoveg");
      }
      setSzoveg("");
      belepesKeres();
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
      setWorkflowState(dontes.current_state || null);
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

              {belepesFuggoben ? (
                <section className="flex min-h-[500px] flex-col justify-center px-6 py-10 sm:px-12">
                  <button
                    type="button"
                    onClick={kezdoAllapotVisszaallitasa}
                    className="mb-8 w-fit text-xs font-semibold text-slate-400 hover:text-amber-100"
                  >
                    ← Vissza a kezdéshez
                  </button>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-300/70">
                    Védett személyes folyamat
                  </p>
                  <h3 className="mt-3 max-w-xl font-serif text-3xl leading-tight text-white">
                    A CV feldolgozásához fiók szükséges.
                  </h3>
                  <p className="mt-4 max-w-xl text-sm leading-6 text-slate-400">
                    A CV személyes adatokat tartalmaz. A fiók biztosítja, hogy
                    csak te férj hozzá a feltöltött dokumentumhoz és a mentett
                    karrierutadhoz.
                  </p>
                  <div className="mt-7 flex flex-wrap items-center gap-4">
                    <Link
                      href={belepesUrl("/")}
                      className="rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200"
                    >
                      Belépés vagy regisztráció
                    </Link>
                    <span className="text-xs text-slate-500">
                      Belépés után itt folytatod.
                    </span>
                  </div>
                </section>
              ) : kezdoValasztas === "cv" && belepve ? (
                <section className="min-h-[500px] px-5 py-6 sm:px-8 sm:py-8">
                  <button
                    type="button"
                    onClick={kezdoAllapotVisszaallitasa}
                    disabled={kuldesFolyamatban}
                    className="text-xs font-semibold text-slate-400 hover:text-amber-100 disabled:opacity-40"
                  >
                    ← Másik út választása
                  </button>

                  <div className="mt-8">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-300/70">
                      Van CV-m
                    </p>
                    <h3 className="mt-3 font-serif text-2xl text-white sm:text-3xl">
                      Mit szeretnél a meglévő CV-ddel?
                    </h3>
                    <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
                      Semmit nem indítunk el automatikusan. Válassz célt, Flow
                      pedig csak a szükséges következő lépést mutatja.
                    </p>
                  </div>

                  {!cvMuvelet ? (
                    <div className="mt-7 grid gap-3 md:grid-cols-3">
                      {CV_MUVELETEK.map((muvelet) => (
                        <button
                          key={muvelet.id}
                          type="button"
                          onClick={() => cvMuveletValasztasa(muvelet)}
                          disabled={kuldesFolyamatban}
                          className="group min-h-40 rounded-2xl border border-white/10 bg-white/[0.025] p-5 text-left hover:-translate-y-0.5 hover:border-amber-300/35 hover:bg-amber-300/[0.05] disabled:opacity-50"
                        >
                          <span className="text-sm font-semibold text-slate-100 group-hover:text-amber-100">
                            {muvelet.cim}
                          </span>
                          <span className="mt-3 block text-xs leading-5 text-slate-500">
                            {muvelet.leiras}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-7">
                      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/8 pb-4">
                        <div>
                          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                            Kiválasztott cél
                          </p>
                          <p className="mt-1 text-sm font-semibold text-amber-100">
                            {
                              CV_MUVELETEK.find(
                                (muvelet) => muvelet.id === cvMuvelet,
                              )?.cim
                            }
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setCvMuvelet(null);
                            setWorkflowState(null);
                          }}
                          className="text-xs font-semibold text-slate-400 hover:text-amber-100"
                        >
                          Módosítás
                        </button>
                      </div>

                      {[
                        "CEL_TISZTAZOTT",
                        "PROFIL_HIANYOS",
                        "PROFIL_ELLENORZOTT",
                      ].includes(workflowState) && (
                        <ProfileGate
                          embedded
                          onStateChange={(result) =>
                            setWorkflowState(
                              result.current_state || workflowState,
                            )
                          }
                        />
                      )}
                    </div>
                  )}

                  {kuldesFolyamatban && (
                    <p className="mt-5 text-sm text-slate-400">
                      A következő lépés előkészítése…
                    </p>
                  )}
                </section>
              ) : (
                <div className="space-y-4 p-5 sm:p-6">
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
                    </div>
                  ))}
                  {kuldesFolyamatban && (
                    <div className="max-w-[82%] rounded-2xl border border-amber-300/12 bg-amber-300/[0.05] px-4 py-3 text-sm text-slate-400">
                      Flow feldolgozza a következő lépést…
                    </div>
                  )}

                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      uzenetKuldese(szoveg);
                    }}
                    className="relative mt-5"
                  >
                    <label htmlFor="flow-message" className="sr-only">
                      Üzenet Flow számára
                    </label>
                    <textarea
                      id="flow-message"
                      value={szoveg}
                      onChange={(event) => setSzoveg(event.target.value)}
                      disabled={!belepve}
                      onKeyDown={(event) => {
                        if (
                          event.key === "Enter" &&
                          !event.shiftKey &&
                          !event.nativeEvent.isComposing
                        ) {
                          event.preventDefault();
                          uzenetKuldese(szoveg);
                        }
                      }}
                      placeholder={
                        belepve
                          ? "Írd le néhány mondatban, hol tartasz és miben segítsek…"
                          : "A személyes Flow-beszélgetéshez jelentkezz be."
                      }
                      rows={7}
                      maxLength={4000}
                      className="min-h-44 w-full resize-y rounded-2xl border border-white/12 bg-slate-950/55 px-5 py-4 pb-16 text-sm leading-6 text-white placeholder:text-slate-500 focus:border-amber-300/50 disabled:cursor-not-allowed disabled:opacity-60"
                    />
                    <div className="absolute bottom-4 left-5 text-[11px] text-slate-600">
                      Enter: küldés · Shift + Enter: új sor
                    </div>
                    <button
                      type="submit"
                      disabled={
                        !belepve || kuldesFolyamatban || !szoveg.trim()
                      }
                      className="absolute bottom-3 right-3 rounded-xl bg-amber-300 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {kuldesFolyamatban ? "Küldés…" : "Küldés"}
                    </button>
                  </form>

                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3 text-xs leading-5 text-slate-500">
                    <span>
                      A nyitóoldal fiók nélkül böngészhető. Flow személyes
                      segítsége és az adatok mentése bejelentkezést igényel.
                    </span>
                    {!belepve && (
                      <Link
                        href={belepesUrl("/")}
                        className="shrink-0 font-semibold text-amber-200 hover:text-amber-100"
                      >
                        Belépés vagy regisztráció →
                      </Link>
                    )}
                  </div>

                  <div className="pt-1">
                    <p className="mb-3 text-xs font-medium text-slate-500">
                      Vagy indulj egy gyors választással:
                    </p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {KEZDO_LEPESEK.map((lepes) => (
                        <button
                          key={lepes.id}
                          type="button"
                          onClick={() => kezdoLepesValasztasa(lepes)}
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
                  </div>
                </div>
              )}
            </div>

            {hiba && (
              <div className="mt-4 rounded-2xl border border-red-300/20 bg-red-300/[0.06] px-4 py-3 text-sm text-red-100">
                {hiba}
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

