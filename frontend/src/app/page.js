"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AuthMenu from "./AuthMenu";
import FolyamatPanel from "./FolyamatPanel";
import ProfileGate from "./ProfileGate";
import { apiFetch, publicApiFetch } from "../lib/api";
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

// A kulcsok a backend career_gps_snapshots.terulet értékei, a `kesz` és
// `folyamatban` listák pedig az adott területre a tábla CHECK-jében
// ténylegesen engedélyezett allapot-értékek. A szótár területenként eltér
// (supabase/migrations/20260724072136_flow_career_gps_foundation.sql), ezért
// nem egyetlen közös halmazzal dolgozunk.
const GPS_TERULETEK = [
  {
    kulcs: "karriercel",
    nev: "Cél és irány",
    zartLeiras: "Válassz egy kiindulási módot.",
    kesz: ["kivalasztott", "validalt"],
    folyamatban: ["nyitott"],
  },
  {
    kulcs: "profil",
    nev: "Karrierprofil",
    zartLeiras: "A cél kiválasztása után nyílik meg.",
    kesz: ["megerositett"],
    folyamatban: ["vazlat", "ellenorzendo"],
  },
  {
    kulcs: "piaci_kep",
    nev: "Piaci illeszkedés",
    zartLeiras: "Ellenőrzött profil után nyílik meg.",
    kesz: ["betoltve"],
    folyamatban: ["elavult"],
  },
  {
    kulcs: "felkeszultseg",
    nev: "Felkészültség",
    zartLeiras: "A piaci kép után nyílik meg.",
    kesz: ["megfelelo"],
    folyamatban: ["hianyok", "terv", "folyamatban"],
  },
  {
    kulcs: "palyazas",
    nev: "Pályázati csomag",
    zartLeiras: "Az utolsó lépés.",
    kesz: ["anyag_kesz", "beadas_kovetese"],
    folyamatban: ["nincs_shortlist", "shortlist"],
  },
];

const KEZDO_UZENET = {
  szerep: "flow",
  szoveg:
    "Szia, Flow vagyok, a személyes karrierasszisztensed. Segítek átnézni vagy elkészíteni a CV-det, megtalálni a hozzád illő állásokat, és végigvezetlek a jelentkezés lépésein.",
};

// Vendégként (be nem jelentkezve) Flow csak az oldal általános
// működéséről tud beszélgetni, a valódi, személyre szabott segítséghez
// belépés vagy regisztráció kell -- ezt a köszöntő is jelzi.
const VENDEG_UZENET = {
  szerep: "flow",
  szoveg:
    "Szia, örülök, hogy itt vagy! Kérlek jelentkezz be, vagy regisztrálj, hogy tudjak segíteni. Addig is szívesen mesélek arról, hogyan működik az oldal.",
};

function vendegMeghivoUzenet(cim) {
  return (
    `„${cim}” — ehhez már a saját, biztonságos profilod kell, hogy pontosan ` +
    "neked szóljon a segítség. Jelentkezz be, vagy regisztrálj egy percben, és onnan folytatjuk, ahol most abbahagytuk."
  );
}

export default function Home() {
  const router = useRouter();
  const [session, setSession] = useState(undefined);
  const [uzenetek, setUzenetek] = useState([VENDEG_UZENET]);
  const [szoveg, setSzoveg] = useState("");
  const [kuldesFolyamatban, setKuldesFolyamatban] = useState(false);
  const [hiba, setHiba] = useState(null);
  const [workflowState, setWorkflowState] = useState(null);
  const [gpsNyitva, setGpsNyitva] = useState(false);
  const [gpsTeruletek, setGpsTeruletek] = useState({});
  const [valaszthatoLepesek, setValaszthatoLepesek] = useState([]);
  const [kezdoValasztas, setKezdoValasztas] = useState(null);
  const [cvMuvelet, setCvMuvelet] = useState(null);
  const [futoMuvelet, setFutoMuvelet] = useState(null);
  const [udvozloIrasAlatt, setUdvozloIrasAlatt] = useState(true);
  const kezdoValasztasRef = useRef(null);
  const folytatasRef = useRef(false);
  const flowPanelRef = useRef(null);
  const uzenetVegeRef = useRef(null);
  const elsoRenderRef = useRef(true);
  const bejelentkezesUdvozoltRef = useRef(false);
  const belepesMegorzendoRef = useRef(null);
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

  // A GPS-panel a szerveroldali projekcióból frissül. Minden olyan művelet
  // után újrakérjük, ami eseményt rögzíthetett -- így a panel sosem a kliens
  // találgatása, hanem a backend rögzített állapota.
  const gpsFrissites = useCallback(async () => {
    try {
      const valasz = await apiFetch("/api/v1/career-gps");
      if (!valasz.ok) return;
      const adat = await valasz.json();
      const terkep = {};
      for (const sor of adat.teruletek || []) {
        terkep[sor.terulet] = sor.allapot;
      }
      setGpsTeruletek(terkep);
    } catch {
      // A GPS-panel kiegészítő nézet: ha nem elérhető, a folyamat mehet tovább.
    }
  }, []);

  useEffect(() => {
    if (!session) return;
    apiFetch("/api/v1/profile")
      .then((response) => (response.ok ? response.json() : null))
      .then((profile) => {
        if (!profile) return;
        if (profile.current_state) setWorkflowState(profile.current_state);
        setValaszthatoLepesek(profile.available_actions || []);
      })
      .catch(() => {});
    gpsFrissites();
  }, [session, gpsFrissites]);

  // Kijelentkezéskor a komponens nem mountolódik újra, ezért a folyamat
  // kliensoldali nyomait kifejezetten törölni kell -- különben a kilépett
  // felhasználó a belépésre váró panelen ragad, a következő belépő pedig
  // az előző választásait örökölné.
  useEffect(() => {
    if (session !== null) return;
    folytatasRef.current = false;
    bejelentkezesUdvozoltRef.current = false;
    kezdoValasztasRef.current = null;
    setKezdoValasztas(null);
    setCvMuvelet(null);
    setWorkflowState(null);
    setGpsTeruletek({});
    setValaszthatoLepesek([]);
    setUzenetek([VENDEG_UZENET]);
    setSzoveg("");
    setHiba(null);
  }, [session]);

  // Bejelentkezéskor a vendég-köszöntőt lecseréljük a személyes Flow
  // köszöntőre -- de csak egyszer, és csak ha a beszélgetés még a
  // kiinduló üdvözlésnél tart (egy folyamatban lévő beszélgetést nem
  // törlünk el, ha a munkamenet csak frissül a háttérben).
  useEffect(() => {
    if (!session || bejelentkezesUdvozoltRef.current) return;
    bejelentkezesUdvozoltRef.current = true;
    setUzenetek((elozo) =>
      elozo.length === 1 && elozo[0] === VENDEG_UZENET ? [KEZDO_UZENET] : elozo,
    );
  }, [session]);

  useEffect(() => {
    if (!session || folytatasRef.current) return;

    // A belépés előtt begépelt üzenet visszakerül a mezőbe. Szándékosan
    // nem küldjük el automatikusan: a modellhívás pénzbe kerül, azt a
    // felhasználó indítsa el kifejezetten.
    const megorzottUzenet = window.localStorage.getItem(
      "career_pending_message",
    );
    if (megorzottUzenet) {
      window.localStorage.removeItem("career_pending_message");
      setSzoveg(megorzottUzenet);
    }

    const fuggoben = window.localStorage.getItem("career_pending_start");
    if (fuggoben !== "cv") return;

    folytatasRef.current = true;
    window.localStorage.removeItem("career_pending_start");
    kezdoValasztasRef.current = "cv";
    setKezdoValasztas("cv");
  }, [session]);

  // Amikor egyetlen (kezdő) üzenetre esik vissza a beszélgetés -- új
  // látogatáskor, be- vagy kijelentkezéskor, "Másik út választása" után --
  // Flow rövid ideig "ír", mielőtt az üzenet megjelenik. Ettől az oldal az
  // első pillanattól élőnek hat, nem statikus szövegnek.
  useEffect(() => {
    if (uzenetek.length !== 1) return;
    setUdvozloIrasAlatt(true);
    const idozito = setTimeout(() => setUdvozloIrasAlatt(false), 1100);
    return () => clearTimeout(idozito);
  }, [uzenetek]);

  // A Flow-panel 500 pixelnél magasabb, ezért nézetváltáskor a változás
  // könnyen a képernyőn kívülre esik: a felhasználó kattint, dolgozik a
  // rendszer, de ő ebből semmit nem lát. Ezért minden nézetváltásnál a
  // panel tetejére görgetünk -- az első betöltéskor viszont nem, mert ott
  // nincs mit megmutatni.
  useEffect(() => {
    if (elsoRenderRef.current) {
      elsoRenderRef.current = false;
      return;
    }
    flowPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [kezdoValasztas, cvMuvelet]);

  // Új üzenetnél a beszélgetés aljára: enélkül Flow válasza a látható
  // terület fölött jelenik meg, és úgy tűnik, mintha semmi nem történt volna.
  useEffect(() => {
    if (uzenetek.length <= 1) return;
    uzenetVegeRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [uzenetek, kuldesFolyamatban]);

  const gpsLepesek = useMemo(() => {
    let elsoNyitottMegvolt = false;
    return GPS_TERULETEK.map((terulet) => {
      const allapot = gpsTeruletek[terulet.kulcs];
      if (terulet.kesz.includes(allapot)) return { ...terulet, allapot: "kesz" };
      if (terulet.folyamatban.includes(allapot)) {
        elsoNyitottMegvolt = true;
        return { ...terulet, allapot: "folyamatban" };
      }
      if (!elsoNyitottMegvolt) {
        elsoNyitottMegvolt = true;
        return { ...terulet, allapot: "aktiv" };
      }
      return { ...terulet, allapot: "zart" };
    });
  }, [gpsTeruletek]);

  const keszSzazalek = useMemo(() => {
    const kesz = gpsLepesek.filter((lepes) => lepes.allapot === "kesz").length;
    return Math.round((kesz / gpsLepesek.length) * 100);
  }, [gpsLepesek]);

  const kovetkezoLepes = useMemo(
    () => gpsLepesek.find((lepes) => lepes.allapot !== "kesz") || null,
    [gpsLepesek],
  );

  const gpsStatusz = useMemo(() => {
    if (!belepve) return "Vendég mód";
    if (keszSzazalek === 100) return "Karrierút összeállt";
    return keszSzazalek > 0 ? `${keszSzazalek}% kész` : "Profilindításra kész";
  }, [belepve, keszSzazalek]);

  // Vendégként a saját belépőoldalra visszük. A választás a böngészőben
  // marad, és belépés után onnan folytatjuk. Csak kifejezett CTA-gombra
  // hívjuk -- vendégként a kattintás önmagában NEM navigál el, Flow előbb
  // szól, és a döntés a felhasználóé marad.
  function belepesreKuldes(mod = "belepes") {
    const megorzendo = belepesMegorzendoRef.current;
    if (megorzendo) {
      for (const [kulcs, ertek] of Object.entries(megorzendo)) {
        window.localStorage.setItem(kulcs, ertek);
      }
    }
    belepesMegorzendoRef.current = null;
    router.push(`/login?next=%2F&mod=${mod}`);
  }

  // Vendégként a "gyors választás" gombok nem navigálnak el azonnal: Flow
  // előbb egy meleg, magyarázó üzenettel invitál a belépésre/regisztrációra,
  // a döntés a felhasználóé. A választás a böngészőben megmarad, hogy
  // belépés után pontosan onnan folytathassuk.
  function ctaMeghivas(megorzendo, flowSzoveg) {
    belepesMegorzendoRef.current = megorzendo;
    setUzenetek((elozo) => [
      ...elozo,
      { szerep: "flow", szoveg: flowSzoveg, cta: true },
    ]);
  }

  function kezdoLepesValasztasa(lepes) {
    if (kezdoValasztasRef.current || kuldesFolyamatban) return;

    if (!belepve) {
      ctaMeghivas(
        lepes.id === "cv"
          ? { career_pending_start: "cv" }
          : { career_pending_message: lepes.cim },
        vendegMeghivoUzenet(lepes.cim),
      );
      return;
    }

    kezdoValasztasRef.current = lepes.id;
    setKezdoValasztas(lepes.id);
    if (lepes.id === "cv") return;
    uzenetKuldese(lepes.cim);
  }

  async function cvMuveletValasztasa(muvelet) {
    if (cvMuvelet || kuldesFolyamatban) return;
    setHiba(null);
    setFutoMuvelet(muvelet.id);
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
      setValaszthatoLepesek(dontes.available_actions || []);
      gpsFrissites();
    } catch {
      setHiba("A CV-művelet indítása nem sikerült. Próbáld újra.");
    } finally {
      setFutoMuvelet(null);
      setKuldesFolyamatban(false);
    }
  }

  async function kezdoAllapotVisszaallitasa() {
    if (kuldesFolyamatban) return;
    setKuldesFolyamatban(true);
    setHiba(null);
    if (belepve && kezdoValasztas === "cv") {
      try {
        const response = await apiFetch("/api/v1/workflow/reset", {
          method: "POST",
        });
        if (!response.ok) {
          throw new Error(`workflow-reset: ${response.status}`);
        }
      } catch {
        setHiba("A visszalépés nem sikerült. Próbáld újra.");
        setKuldesFolyamatban(false);
        return;
      }
    }
    window.localStorage.removeItem("career_pending_start");
    window.localStorage.removeItem("career_pending_cv_import");
    window.localStorage.removeItem("career_pending_message");
    kezdoValasztasRef.current = null;
    setKezdoValasztas(null);
    setCvMuvelet(null);
    setWorkflowState(null);
    setValaszthatoLepesek([]);
    setUzenetek([KEZDO_UZENET]);
    setSzoveg("");
    setHiba(null);
    setKuldesFolyamatban(false);
    gpsFrissites();
  }

  async function uzenetKuldese(uzenetSzoveg) {
    const tiszta = uzenetSzoveg.trim();
    if (!tiszta || kuldesFolyamatban) return;

    setHiba(null);
    setUzenetek((elozo) => [...elozo, { szerep: "user", szoveg: tiszta }]);
    setSzoveg("");
    setKuldesFolyamatban(true);

    if (!belepve) {
      // Vendégmódban Flow csak az oldal általános működéséről beszélhet, a
      // szerver szűk, ingyenes prompttal válaszol -- nincs profil, nincs
      // előzmény, nincs fizetős modellhívás. A valódi segítséghez a válasz
      // mindig belépésre/regisztrációra invitál.
      try {
        const valasz = await publicApiFetch("/api/v1/flow/guest-messages", {
          method: "POST",
          body: JSON.stringify({ kerdes: tiszta }),
        });
        if (!valasz.ok) throw new Error(`flow-guest-messages: ${valasz.status}`);
        const dontes = await valasz.json();
        belepesMegorzendoRef.current = null;
        setUzenetek((elozo) => [
          ...elozo,
          { szerep: "flow", szoveg: dontes.valasz || "", cta: true },
        ]);
      } catch {
        setHiba(
          "Flow most nem érte el a háttérrendszert. Próbáld újra kicsit később.",
        );
      } finally {
        setKuldesFolyamatban(false);
      }
      return;
    }

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
      if (dontes.gps_esemeny) gpsFrissites();
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
          <span className="font-semibold text-amber-200">{keszSzazalek}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/8">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-200 transition-[width] duration-500"
            style={{ width: `${Math.max(keszSzazalek, 3)}%` }}
          />
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">
          Nem becsülünk találomra. A sáv csak ellenőrzött lépések után halad.
        </p>
      </div>

      <ol className="space-y-1">
        {gpsLepesek.map((lepes, index) => (
          <li key={lepes.kulcs} className="relative flex gap-3 pb-4">
            {index < gpsLepesek.length - 1 && (
              <span
                className={`absolute left-[13px] top-7 h-[calc(100%_-_18px)] w-px ${
                  lepes.allapot === "kesz" ? "bg-emerald-300/35" : "bg-white/10"
                }`}
              />
            )}
            <span
              className={`relative z-10 mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[10px] font-bold ${
                lepes.allapot === "kesz"
                  ? "border-emerald-300/50 bg-emerald-300/15 text-emerald-200"
                  : lepes.allapot === "folyamatban"
                    ? "flow-pulse border-amber-300/60 bg-amber-300/20 text-amber-100"
                    : lepes.allapot === "aktiv"
                      ? "flow-pulse border-amber-300/60 bg-amber-300 text-slate-950"
                      : "border-white/12 bg-slate-950/70 text-slate-500"
              }`}
            >
              {lepes.allapot === "kesz" ? "✓" : String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <p
                className={`text-sm font-medium ${
                  lepes.allapot === "kesz"
                    ? "text-emerald-100"
                    : lepes.allapot === "zart"
                      ? "text-slate-400"
                      : "text-amber-100"
                }`}
              >
                {lepes.nev}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {lepes.allapot === "kesz"
                  ? "Ellenőrzött és rögzített."
                  : lepes.allapot === "folyamatban"
                    ? "Megkezdve, még nincs jóváhagyva."
                    : lepes.allapot === "aktiv"
                      ? lepes.zartLeiras
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
          {!belepve
            ? "A személyes karrierút indításához jelentkezz be."
            : kovetkezoLepes
              ? `${kovetkezoLepes.nev} — ${kovetkezoLepes.zartLeiras}`
              : "Minden szakasz ellenőrizve. Készen állsz a pályázásra."}
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
            <div
              ref={flowPanelRef}
              className="glass-panel scroll-mt-6 overflow-hidden rounded-3xl"
            >
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

              {kezdoValasztas === "cv" && belepve ? (
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
                          aria-busy={futoMuvelet === muvelet.id}
                          className={`group min-h-40 rounded-2xl border p-5 text-left transition ${
                            futoMuvelet === muvelet.id
                              ? "border-amber-300/60 bg-amber-300/10"
                              : "border-white/10 bg-white/[0.025] hover:-translate-y-0.5 hover:border-amber-300/35 hover:bg-amber-300/[0.05]"
                          } ${
                            futoMuvelet && futoMuvelet !== muvelet.id
                              ? "opacity-30"
                              : ""
                          } disabled:cursor-not-allowed`}
                        >
                          <span
                            className={`text-sm font-semibold ${
                              futoMuvelet === muvelet.id
                                ? "text-amber-100"
                                : "text-slate-100 group-hover:text-amber-100"
                            }`}
                          >
                            {muvelet.cim}
                          </span>
                          <span className="mt-3 block text-xs leading-5 text-slate-500">
                            {futoMuvelet === muvelet.id ? (
                              <span className="inline-flex items-center gap-2 text-amber-200/80">
                                <span className="flow-pulse h-1.5 w-1.5 rounded-full bg-amber-300" />
                                Indítás…
                              </span>
                            ) : (
                              muvelet.leiras
                            )}
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
                          onStateChange={(result) => {
                            setWorkflowState(
                              result.current_state || workflowState,
                            );
                            setValaszthatoLepesek(
                              result.available_actions || [],
                            );
                            gpsFrissites();
                          }}
                        />
                      )}

                      <FolyamatPanel
                        availableActions={valaszthatoLepesek}
                        onStateChange={(result) => {
                          setWorkflowState(result.current_state);
                          setValaszthatoLepesek(result.available_actions || []);
                          gpsFrissites();
                        }}
                      />
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
                  {uzenetek.length === 1 && udvozloIrasAlatt && (
                    <div className="flex max-w-[82%] items-center gap-2.5 rounded-2xl border border-amber-300/12 bg-amber-300/[0.05] px-4 py-3 text-sm text-slate-400">
                      <span className="flow-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                      Flow ír…
                    </div>
                  )}
                  {!(uzenetek.length === 1 && udvozloIrasAlatt) &&
                    uzenetek.map((uzenet, index) => (
                    <div key={`${uzenet.szerep}-${index}`}>
                      <div
                        className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-6 sm:max-w-[82%] ${
                          uzenet.szerep === "flow"
                            ? "border border-amber-300/12 bg-amber-300/[0.05] text-slate-200"
                            : "ml-auto bg-slate-100 text-slate-950"
                        }`}
                      >
                        {uzenet.szoveg}
                      </div>
                      {uzenet.cta && index === uzenetek.length - 1 && (
                        <div className="mt-3 flex flex-wrap gap-2.5">
                          <button
                            type="button"
                            onClick={() => belepesreKuldes("belepes")}
                            className="rounded-full bg-amber-300 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-amber-200"
                          >
                            Bejelentkezés
                          </button>
                          <button
                            type="button"
                            onClick={() => belepesreKuldes("regisztracio")}
                            className="rounded-full border border-amber-300/40 bg-amber-300/10 px-4 py-2 text-xs font-semibold text-amber-100 hover:border-amber-200 hover:bg-amber-300/15"
                          >
                            Regisztráció
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                  {kuldesFolyamatban && (
                    <div className="flex max-w-[82%] items-center gap-2.5 rounded-2xl border border-amber-300/12 bg-amber-300/[0.05] px-4 py-3 text-sm text-slate-400">
                      <span className="flow-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                      Flow feldolgozza a következő lépést…
                    </div>
                  )}
                  <div ref={uzenetVegeRef} />

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
                          : "Kérdezz Flow-tól arról, hogyan működik az oldal…"
                      }
                      rows={7}
                      maxLength={belepve ? 4000 : 600}
                      className="min-h-44 w-full resize-y rounded-2xl border border-white/12 bg-slate-950/55 px-5 py-4 pb-16 text-sm leading-6 text-white placeholder:text-slate-500 focus:border-amber-300/50 disabled:cursor-not-allowed disabled:opacity-60"
                    />
                    <div className="absolute bottom-4 left-5 text-[11px] text-slate-600">
                      Enter: küldés · Shift + Enter: új sor
                    </div>
                    <button
                      type="submit"
                      disabled={kuldesFolyamatban || !szoveg.trim()}
                      className="absolute bottom-3 right-3 rounded-xl bg-amber-300 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {kuldesFolyamatban ? "Küldés…" : "Küldés"}
                    </button>
                  </form>

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
