"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AuthMenu from "./AuthMenu";
import FolyamatPanel, { Eredmeny as FlowEredmeny } from "./FolyamatPanel";
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
];

const CV_ELLENORZES_MUVELET = {
  id: "ellenorzes",
  intent: "cv_ellenorzes",
  cim: "Nézd át a CV-met",
  kerdes: "A meglévő CV-met szeretném ellenőrizni, átírás nélkül.",
};

const PIAC_MUVELET = {
  id: "piac",
  intent: "piaci_korkep",
  cim: "Mutasd a piacot",
  kerdes: "Előbb a célmunkaköröm piaci helyzetét szeretném látni.",
};

// A KIRAKAT: mit tudunk. A látogatót nem az érdekli, hol tartunk az
// építéssel, hanem hogy mit kap. Korábban itt „adatkapcsolat következik" és
// „tervezés alatt" állt -- az fejlesztői jegyzet, nem látogatói információ.
//
// Ez bemutatás, nem menü: nem gomb, nem indít semmit. A belépés utáni
// felületen nem jelenik meg, ott Flow vezet.
const MODULOK = [
  {
    nev: "Van CV-m",
    jel: "01",
    allapot: "Átnézzük, megmutatjuk, mit mondj szakmai nyelven, és mi maradt ki.",
  },
  {
    nev: "Nincs CV-m",
    jel: "02",
    allapot: "Rövid beszélgetésből építünk ellenőrizhető karrierprofilt.",
  },
  {
    nev: "Pályaváltás",
    jel: "03",
    allapot: "Mely szakmákba vihető át a tudásod, és mi hiányzik hozzá.",
  },
  {
    nev: "Piaci körkép",
    jel: "04",
    allapot: "Van-e kereslet, mennyit fizetnek — valódi hirdetésekből.",
  },
  {
    nev: "Álláslehetőségek",
    jel: "05",
    allapot: "Hozzád illő állások, illeszkedés szerint rangsorolva.",
  },
  {
    nev: "Képzések",
    jel: "06",
    allapot: "Mit tanulj meg ahhoz, amit el akarsz érni.",
  },
  {
    nev: "Portfólió",
    jel: "07",
    allapot: "Megmutatható munkákból önálló bemutatkozó oldal.",
  },
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

// Ha a szerver köszöntése nem érkezik meg (hálózati hiba, üres válasz,
// Google-átirányítás utáni furcsaság), Flow akkor sem maradhat néma: a
// belépett felhasználó azt hinné, elromlott az oldal.
//
// A keresztnév a munkamenetből jön -- azt belépés után biztosan tudjuk,
// modellhívás nélkül is.
function tartalekKoszontes() {
  // NÉV NÉLKÜL köszönünk, ha a szerver köszöntése nem érkezett meg.
  //
  // A Google `given_name` mezője magyarul megbízhatatlan: sokan a
  // vezetéknevüket írják a „keresztnév" rovatba. Mérve: Varga Andrea
  // fiókjában a `given_name` = „Varga". Rossz néven szólítani rosszabb,
  // mint név nélkül -- a nevet a megszólítás-mező kérdezi meg.
  return {
    szerep: "flow",
    szoveg:
      "Szia! Örülök, hogy itt vagy. Kezdjünk a legegyszerűbbel: " +
      "van kész önéletrajzod?",
    valaszlehetosegek: ["Van CV-m", "Nincs CV-m"],
  };
}

// Belépés után nincs beégetett kezdőszöveg: Flow köszöntése a szerverről
// jön, néven szólítva. Ez formálja üzenetté a válaszát.
function koszontoUzenet(adat) {
  return {
    szerep: "flow",
    szoveg: adat.uzenet,
    gepel: true,
    nevetKer: Boolean(adat.megszolitas_hianyzik),
    nevJavaslatok: adat.nev_javaslatok || [],
    // FLOW KÉRDEZ, ÉS A VÁLASZOK AZ ÜZENETE ALATT VANNAK.
    //
    // Ugyanaz a mező, amit a beszélgetés válaszai is használnak, tehát a
    // megjelenítés is ugyanaz. Eddig a köszöntés nem adta át, ezért belépés
    // után a felhasználó a kártyarács előtt állt: neki kellett kitalálnia,
    // melyik esetben van. A gombok a szerverről jönnek, kódból eldöntve.
    valaszlehetosegek:
      adat.valaszlehetosegek || ["Van CV-m", "Nincs CV-m"],
  };
}

function belepesUzenetek(adat) {
  const tarolt = Array.isArray(adat?.uzenetek)
    ? adat.uzenetek
        .filter(
          (uzenet) =>
            ["user", "flow"].includes(uzenet?.szerep) &&
            typeof uzenet?.szoveg === "string" &&
            uzenet.szoveg.trim(),
        )
        .map((uzenet) => ({ ...uzenet, gepel: false }))
    : [];

  if (!tarolt.length) {
    return [
      koszontoUzenet({
        ...(adat || {}),
        uzenet: adat?.uzenet || tartalekKoszontes().szoveg,
      }),
    ];
  }

  let utolsoFlow = -1;
  for (let index = tarolt.length - 1; index >= 0; index -= 1) {
    if (tarolt[index].szerep === "flow") {
      utolsoFlow = index;
      break;
    }
  }
  if (utolsoFlow < 0) return tarolt;

  tarolt[utolsoFlow] = {
    ...tarolt[utolsoFlow],
    gepel: Boolean(adat?.uj_koszontes),
    nevetKer: Boolean(adat?.megszolitas_hianyzik),
    nevJavaslatok: adat?.nev_javaslatok || [],
    valaszlehetosegek: adat?.valaszlehetosegek || [],
  };
  return tarolt;
}

// Vendégként Flow maga köszönt, betűnként kiírva. Fix szöveg, nincs
// mögötte modellhívás.
const VENDEG_UZENET = {
  szerep: "flow",
  szoveg: [
    "Szia, Flow vagyok, a személyes MI-karrierasszisztensed.",
    "Nem csak egy önéletrajzot készítek neked. Célzott kérdésekkel segítek felszínre hozni azokat a feladatokat és készségeket is, amelyeket nap mint nap használtál, mégis kimaradhattak a CV-dből. A tapasztalataidat világosan és szakmailag fogalmazom meg, hogy a munkáltatók felismerjék a valódi értéküket.",
    "Megmutatom, hol van rád kereslet és milyen állások illenek hozzád. Ha pályaváltáson gondolkodsz, azt is, mely rokon szakmákba vihető át a tudásod, és hol nyílik rendszeresen több lehetőség – így azt is láthatod, merre van reális esélyed továbblépni.",
    // A rövidítés marad, de mellette ott a magyarázat: aki évek után lép
    // vissza a munkaerőpiacra, annak az „ATS" és a „robotszűrő" is új szó.
    "Átvizsgálom és ATS-re (robotszűrőre) optimalizálom a CV-det – ez az a rendszer, amely a cégeknél gyakran előbb olvassa el az önéletrajzodat, mint egy ember. Célzott motivációs levelet készítek, felépítem a portfóliódat, piaci körképet adok, és valódi álláshirdetések alapján végigvezetlek a jelentkezésig.",
    "Mondd el, hol tartasz most, és hová szeretnél eljutni. Ha regisztrálsz, megőrzöm az előzményeidet, így mindig pontosan onnan folytatjuk, ahol abbahagytuk.",
  ].join("\n\n"),
  gepel: true,
  rendszerKoszonto: true,
  // A teljes bemutatkozás legfeljebb 4,5 másodperc alatt jelenjen meg.
  // Korábban karakterenként 60 ms volt: ez ennél a hosszú szövegnél több
  // mint egy perc várakozást jelentett.
  gepelMaxIdotartamMs: 4500,
};

const VENDEG_CHAT_KULCS = "career_guest_chat";

function ujAtadasAzonosito() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bajtok = new Uint8Array(16);
  window.crypto.getRandomValues(bajtok);
  bajtok[6] = (bajtok[6] & 0x0f) | 0x40;
  bajtok[8] = (bajtok[8] & 0x3f) | 0x80;
  const hex = [...bajtok].map((bajt) => bajt.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10).join(""),
  ].join("-");
}

function vendegAtadasOlvasasa() {
  if (typeof window === "undefined") return null;
  try {
    const nyers = window.localStorage.getItem(VENDEG_CHAT_KULCS);
    if (!nyers) return null;
    const ertelmezett = JSON.parse(nyers);
    if (Array.isArray(ertelmezett)) {
      const atadas = {
        verzio: 1,
        azonosito: ujAtadasAzonosito(),
        uzenetek: ertelmezett,
      };
      window.localStorage.setItem(VENDEG_CHAT_KULCS, JSON.stringify(atadas));
      return atadas;
    }
    if (
      ertelmezett &&
      typeof ertelmezett.azonosito === "string" &&
      Array.isArray(ertelmezett.uzenetek)
    ) {
      return ertelmezett;
    }
  } catch {
    // Sérült böngészőadatot nem adunk tovább.
  }
  return null;
}

function vendegAtadasMentese(uzenetek) {
  if (typeof window === "undefined") return;
  const mentendo = uzenetek
    .filter(
      (uzenet) =>
        ["user", "flow"].includes(uzenet.szerep) &&
        !uzenet.rendszerKoszonto &&
        typeof uzenet.szoveg === "string" &&
        uzenet.szoveg.trim(),
    )
    .slice(-6)
    .map((uzenet) => ({
      szerep: uzenet.szerep,
      szoveg: uzenet.szoveg.slice(0, 600),
    }));
  if (!mentendo.length) return;
  const korabbi = vendegAtadasOlvasasa();
  window.localStorage.setItem(
    VENDEG_CHAT_KULCS,
    JSON.stringify({
      verzio: 1,
      azonosito: korabbi?.azonosito || ujAtadasAzonosito(),
      uzenetek: mentendo,
    }),
  );
}

// Mi legyen a vendégfelületen. Három eset, ebben a sorrendben.
//
// A jelzőt a belépő oldalra navigálás teszi le, a sikeres belépés törli, és
// a böngésző bezárásával is elmúlik (sessionStorage).
//
// 1. Félbehagyta a belépést ÉS beszélgettek: a beszélgetés folytatódik.
//    Amit a látogató írt, az nem tűnhet el csak azért, mert megnézte a
//    regisztrációs oldalt.
// 2. Félbehagyta a belépést, de nem beszélgettek: ugyanaz a köszöntő,
//    gépelés nélkül.
// 3. Minden más (friss látogató, kijelentkezés utáni tiszta lap): a
//    köszöntő, gépelve, ahogy eddig.
function vendegKezdoUzenetek() {
  if (typeof window === "undefined") return [VENDEG_UZENET];

  // EGY LÁTOGATÁS ALATT ELÉG EGYSZER ELOLVASNI, KI FLOW.
  //
  // A gépelés elsőre figyelemfelkeltő, másodszorra idegesítő -- és ez hosszú
  // szöveg. Aki kilép, belép, majd újra kilép, annak nem kell háromszor
  // végignéznie.
  //
  // `sessionStorage`, tehát a böngésző bezárásával elmúlik: új látogatásnál
  // megint legépeli, ahogy kell.
  const marLatta = window.sessionStorage.getItem("career_bemutatkozas_latott");
  if (!marLatta) {
    window.sessionStorage.setItem("career_bemutatkozas_latott", "1");
    return [VENDEG_UZENET];
  }

  if (!window.sessionStorage.getItem("career_login_probalkozas")) {
    return [{ ...VENDEG_UZENET, gepel: false }];
  }
  try {
    const atadas = vendegAtadasOlvasasa();
    if (atadas?.uzenetek.length) {
      return atadas.uzenetek.map((sor) => ({ ...sor, gepel: false }));
    }
  } catch {
    // Sérült tartalom: a köszöntővel indulunk.
  }
  return [{ ...VENDEG_UZENET, gepel: false }];
}

/** Betűnként jeleníti meg a szöveget, mintha Flow épp írná. Kattintásra
 *  azonnal kiírja a többit; csökkentett animációt kérő beállításnál
 *  eleve nem animál. */
function GepeloSzoveg({ szoveg, sebessegMs = 18, maxIdotartamMs = null }) {
  const [hossz, setHossz] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setHossz(szoveg.length);
      return;
    }
    setHossz(0);
    const idokoz = maxIdotartamMs ? 20 : sebessegMs;
    const lepes = maxIdotartamMs
      ? Math.max(1, Math.ceil(szoveg.length / (maxIdotartamMs / idokoz)))
      : 1;
    const idozito = setInterval(() => {
      setHossz((elozo) =>
        elozo >= szoveg.length ? elozo : Math.min(szoveg.length, elozo + lepes),
      );
    }, idokoz);
    return () => clearInterval(idozito);
  }, [szoveg, sebessegMs, maxIdotartamMs]);

  const kesz = hossz >= szoveg.length;

  return (
    <span
      onClick={() => setHossz(szoveg.length)}
      title={kesz ? undefined : "Kattints a teljes szöveg megjelenítéséhez"}
      className={kesz ? undefined : "cursor-pointer"}
    >
      {szoveg.slice(0, hossz)}
      {!kesz && (
        <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-amber-300/80" />
      )}
    </span>
  );
}

/** Apró mező Flow kérdése alatt: a megszólítás mentése a profilba.
 *  A meglévő vázlat + megerősítés végpontokat használja, tehát ugyanaz
 *  az út, mint bármely más profiladatnál. A nevet szándékosan nem a
 *  modell nyeri ki a mondatból -- azt beírod, és úgy kerül be. */
function MegszolitasMezo({ onKesz, javaslatok = [] }) {
  const [nev, setNev] = useState("");
  const [dolgozik, setDolgozik] = useState(false);
  const [hiba, setHiba] = useState(null);

  async function mentes(event) {
    event.preventDefault();
    const tiszta = nev.trim();
    if (!tiszta || dolgozik) return;
    setDolgozik(true);
    setHiba(null);
    try {
      const vazlat = await apiFetch("/api/v1/profile/draft", {
        method: "PATCH",
        body: JSON.stringify({ fields: { display_name: tiszta } }),
      });
      if (!vazlat.ok) throw new Error("vazlat");
      const megerosites = await apiFetch("/api/v1/profile/confirm", {
        method: "POST",
        body: JSON.stringify({
          fields: ["display_name"],
          reason: "user_confirmation",
        }),
      });
      if (!megerosites.ok) throw new Error("megerosites");
      onKesz(tiszta);
    } catch {
      setHiba("A név mentése nem sikerült. Próbáld újra.");
      setDolgozik(false);
    }
  }

  return (
    <form onSubmit={mentes} className="mt-3 flex flex-wrap items-center gap-2">
      <label
        htmlFor="megszolitas"
        className="w-full text-xs font-medium text-amber-100/80"
      >
        Keresztneved
      </label>
      {javaslatok.length > 0 && (
        <div className="mb-1 flex w-full flex-wrap gap-2">
          {javaslatok.map((javaslat) => (
            <button
              key={javaslat}
              type="button"
              onClick={() => setNev(javaslat)}
              className={`rounded-full border px-3 py-1 text-xs ${
                nev === javaslat
                  ? "border-amber-300/70 bg-amber-300/15 text-amber-100"
                  : "border-white/15 text-slate-300 hover:border-amber-300/40"
              }`}
            >
              {javaslat}
            </button>
          ))}
        </div>
      )}
      <input
        id="megszolitas"
        value={nev}
        onChange={(event) => setNev(event.target.value)}
        maxLength={80}
        autoComplete="off"
        className="min-w-40 flex-1 rounded-xl border border-amber-300/40 bg-slate-950/70 px-3.5 py-2 text-sm text-white focus:border-amber-300/70 focus:outline-none"
      />
      <button
        type="submit"
        disabled={dolgozik || !nev.trim()}
        className="rounded-xl bg-amber-300 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-amber-200 disabled:opacity-40"
      >
        {dolgozik ? "Mentés…" : "Mentés"}
      </button>
      {hiba && <span className="w-full text-xs text-red-200">{hiba}</span>}
    </form>
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
  // A profilban megerősített célmunkakör. Üres string, ha még nincs.
  const [megerositettCel, setMegerositettCel] = useState("");
  const [futoMuvelet, setFutoMuvelet] = useState(null);
  const kezdoValasztasRef = useRef(null);
  const folytatasRef = useRef(false);
  const flowPanelRef = useRef(null);
  const cvFeltoltesRef = useRef(null);
  const uzenetVegeRef = useRef(null);
  const elsoRenderRef = useRef(true);
  const vendegElozmenyRef = useRef([]);
  const udvozoltUserRef = useRef(null);
  const celValasztasRef = useRef(false);
  const celSzabadMegadasRef = useRef(false);
  const belepve = Boolean(session);

  // A CV-LÁNC EGYETLEN ZÁRT FOLYAMAT, TÖBB FÁZISSAL.
  //
  // A `kezdoValasztas` a CV-úton két értéket vesz fel: `"cv"` a feltöltésnél,
  // `"cv-cel"` a célmunkakör tisztázásánál. Aki csak az elsőre szűkít, annak a
  // folyamat közepén szétesik a felület: a jóváhagyás pillanatában újra
  // kinyílik minden más szolgáltatás, pedig a lánc még fut.
  const cvFolyamatAktiv = kezdoValasztas === "cv" || kezdoValasztas === "cv-cel";
  const felhasznaloId = session?.user?.id || null;

  useEffect(() => {
    const supabase = createClient();
    let aktiv = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!aktiv) return;
      // Ha az auth-listener gyorsabban már adott állapotot, a később
      // beérkező kezdeti lekérés ne írja azt felül egy elavult eredménnyel.
      setSession((elozo) => (elozo === undefined ? data.session : elozo));
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (aktiv) setSession(nextSession);
    });
    return () => {
      aktiv = false;
      subscription.unsubscribe();
    };
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
    if (!felhasznaloId) return;
    apiFetch("/api/v1/profile")
      .then((response) => (response.ok ? response.json() : null))
      .then((profile) => {
        if (!profile) return;
        if (profile.current_state) setWorkflowState(profile.current_state);
        setValaszthatoLepesek(profile.available_actions || []);
        // A MEGERŐSÍTETT CÉLMUNKAKÖRT MEG KELL JEGYEZNI, KÜLÖNBEN ÚJRA KÉRDEZZÜK.
        //
        // A válasz eddig is tartalmazta a `confirmed_data`-t, csak senki nem
        // olvasta ki belőle a célt. Emiatt a CV-jóváhagyás után Flow akkor is
        // rákérdezett a célmunkakörre, ha a felhasználó azt már korábban
        // megerősítette (folyamat_terkep.md 3. és 11.4).
        setMegerositettCel(
          String((profile.confirmed_data || {}).target_role || "").trim(),
        );
      })
      .catch(() => {});
    gpsFrissites();
  }, [felhasznaloId, gpsFrissites]);

  // Kijelentkezéskor a komponens nem mountolódik újra, ezért a folyamat
  // kliensoldali nyomait kifejezetten törölni kell -- különben a kilépett
  // felhasználó a belépésre váró panelen ragad, a következő belépő pedig
  // az előző választásait örökölné.
  // KILÉPÉSKOR takarítunk -- és CSAK akkor.
  //
  // Korábban ez az effekt minden olyan esetben lefutott, amikor a munkamenet
  // „nincs belépve" állapotra állt -- tehát vendégként is, minden
  // oldalbetöltéskor. Feltétel nélkül visszaírta a köszöntőt, így Flow újra
  // meg újra bemutatkozott annak, aki csak visszalépett a bejelentkezési
  // oldalról. A `sessionStorage`-os javítás lefutott, ezt viszont nem
  // előzte meg: ez felülírta.
  //
  // Most az előző munkamenetet is nézzük: takarítani csak akkor kell, ha
  // VOLT belépett munkamenet, és megszűnt.
  // A kezdő üzeneteket oldalbetöltésenként EGYSZER döntjük el. A
  // `vendegKezdoUzenetek` beállítja a „már látta" jelzőt, tehát ha többször
  // hívnánk, a második hívás már gépelés nélkülit adna -- és az első
  // látogatásnál elveszne az animáció.
  const vendegKezdoRef = useRef(null);
  const vendegKezdo = useCallback(() => {
    if (!vendegKezdoRef.current) {
      vendegKezdoRef.current = vendegKezdoUzenetek();
    }
    return vendegKezdoRef.current;
  }, []);

  const elozoSessionRef = useRef(undefined);
  useEffect(() => {
    const elozoSession = elozoSessionRef.current;
    elozoSessionRef.current = session;
    if (session !== null) return;

    // A BELÉPETT ÁLLAPOT MARADVÁNYAIT MINDIG TAKARÍTJUK.
    //
    // Ezt korábban a „volt-e előző munkamenet" feltételhez kötöttem, hogy a
    // köszöntő ne íródjon újra. Csakhogy kijelentkezéskor az oldal
    // újratöltődik, és ilyenkor az előző munkamenet üres -- a takarítás
    // kimaradt, és a belépett felület (GPS-panel, lépésgombok) ott ragadt
    // vendégmódban. Éles adat látszott olyannak, aki már nincs bejelentkezve.
    folytatasRef.current = false;
    udvozoltUserRef.current = null;
    kezdoValasztasRef.current = null;
    setKezdoValasztas(null);
    setCvMuvelet(null);
    setWorkflowState(null);
    setGpsTeruletek({});
    setValaszthatoLepesek([]);
    celValasztasRef.current = false;
    celSzabadMegadasRef.current = false;
    setSzoveg("");
    setHiba(null);

    // Az ÜZENETEKET viszont csak akkor írjuk vissza a köszöntőre, ha valóban
    // belépett beszélgetés volt. Így a takarítás nem hozza vissza az újra
    // meg újra legépelt bemutatkozást.
    // Az üzenetek vendégként MINDIG a köszöntőre állnak vissza. Korábban ezt
    // feltételhez kötöttem, és emiatt kijelentkezés után a belépett
    // beszélgetés kint maradt a vendégfelületen.
    void elozoSession;
    setUzenetek(vendegKezdo());
  }, [session]);

  // A köszöntő a komponens kezdőértéke, azt a szerveroldali előrenderelés
  // miatt nem olvashatjuk a böngésző tárolójából (hidratálási hiba lenne).
  // Ezért beillesztés után igazítunk: ha a látogató a belépő oldalról jött
  // vissza, ugyanaz a szöveg marad, csak gépelés nélkül.
  //
  // SZÁNDÉKOSAN `session !== null`, nem `belepve`: a `session` kezdőértéke
  // `undefined` (még nem tudjuk, van-e munkamenet). Ha itt `belepve`-t
  // néztünk volna, ez az effekt minden mountnál lefutott volna, MIELŐTT a
  // belépés utáni takarító effekt (lent) törölhette volna a
  // `career_login_probalkozas` / `career_guest_chat` bejegyzéseket -- így a
  // `vendegKezdo()` a teljes, elavult vendégelőzményt fagyasztotta volna a
  // gyorsítótárba, ami aztán egy későbbi kijelentkezéskor visszaköszönt
  // volna. `session === null` csak akkor igaz, ha MÁR biztosan tudjuk, hogy
  // nincs bejelentkezve senki.
  useEffect(() => {
    if (session !== null) return;
    setUzenetek((elozo) =>
      elozo.length === 1 && elozo[0] === VENDEG_UZENET ? vendegKezdo() : elozo,
    );
  }, [session, vendegKezdo]);

  // A belépés elnavigál a /login oldalra, ezért a React-állapot elveszne.
  // A vendégbeszélgetést a böngészőben őrizzük meg, hogy belépés után
  // ne kelljen elölről kezdeni. Szerverre csak sikeres belépés után kerül.
  useEffect(() => {
    if (belepve || uzenetek.length <= 1) return;
    vendegAtadasMentese(uzenetek);
  }, [uzenetek, belepve]);

  // Felhasználónként egyszer töltjük be a szerveroldali beszélgetést.
  // A Supabase TOKEN_REFRESHED eseménye új session objektumot ad, de attól
  // még ugyanaz az ember marad. Korábban minden ilyen eseménynél kiürítettük
  // az üzeneteket, majd a ref miatt nem töltöttük vissza: ettől tűnt el a
  // Flow-ablak lapváltás után, és ettől hozta vissza az F5.
  useEffect(() => {
    if (!felhasznaloId || udvozoltUserRef.current === felhasznaloId) return;
    udvozoltUserRef.current = felhasznaloId;

    const vendegAtadas = vendegAtadasOlvasasa();
    const vendegSorok = vendegAtadas?.uzenetek || [];
    // A belépés sikerült, tehát a „félbehagyta a regisztrációt" jelző
    // elévült. Ha később kijelentkezik, friss bemutatkozás fogadja.
    window.sessionStorage.removeItem("career_login_probalkozas");

    // Ha az adatbázis-átadás nem sikerülne, az első belépett üzenet még
    // egyszer megkapja háttérként. Sikeres átadásnál lent azonnal kiürítjük.
    if (vendegSorok.length) vendegElozmenyRef.current = vendegSorok;

    setUzenetek([]);
    setKuldesFolyamatban(true);

    // A Google-átirányítás előtt megadott keresztnév mentése. Enélkül
    // hiába írta be a felhasználó: az OAuth-átirányítás eldobta volna.
    const megorzottNev = window.localStorage.getItem(
      "career_pending_given_name",
    );
    const nevMentes = megorzottNev
      ? (async () => {
          // A regisztrációs név két tartós helyre kerül: az auth-metaadatba
          // és a megerősített karrierprofilba. A helyi példányt csak akkor
          // töröljük, ha mindkét mentés sikerült; átmeneti hiba után a
          // következő betöltés újrapróbálja, nem kérdezi meg újra.
          const supabaseNev = createClient();
          const { error: authNevHiba } = await supabaseNev.auth.updateUser({
            data: { sajat_keresztnev: megorzottNev },
          });
          if (authNevHiba) throw authNevHiba;

          const draftValasz = await apiFetch("/api/v1/profile/draft", {
            method: "PATCH",
            body: JSON.stringify({ fields: { display_name: megorzottNev } }),
          });
          if (!draftValasz.ok) throw new Error("display-name-draft");

          const megerositesValasz = await apiFetch("/api/v1/profile/confirm", {
            method: "POST",
            body: JSON.stringify({
              fields: ["display_name"],
              reason: "registration_form",
            }),
          });
          if (!megerositesValasz.ok) throw new Error("display-name-confirm");

          window.localStorage.removeItem("career_pending_given_name");
        })().catch(() => null)
      : Promise.resolve();

    // A Google-belépés előtt adott hozzájárulás nyoma. A `signInWithOAuth`
    // nem tud metaadatot átvinni az átirányításon, ezért a belépési oldal
    // localStorage-ba tette, és itt kerül a profilba. Csak akkor írjuk,
    // ha még nincs: a meglévő nyom dátumát nem szabad felülvágni.
    const nyersHozzajarulas = window.localStorage.getItem(
      "career_pending_gdpr_consent",
    );
    window.localStorage.removeItem("career_pending_gdpr_consent");
    let hozzajarulasMentes = Promise.resolve();
    if (nyersHozzajarulas && !session.user?.user_metadata?.gdpr_consent_version) {
      try {
        hozzajarulasMentes = createClient()
          .auth.updateUser({ data: JSON.parse(nyersHozzajarulas) })
          .catch(() => null);
      } catch {
        // Sérült tartalom: nincs mit menteni.
      }
    }

    // A szerver egyszerre végzi az idempotens vendégátadást és a tartós
    // előzmény visszaolvasását. F5-re nem készít új köszöntést.
    Promise.all([nevMentes, hozzajarulasMentes]).then(() =>
    apiFetch("/api/v1/flow/belepes-utan", {
      method: "POST",
      body: JSON.stringify({
        vendeg_elozmeny: vendegSorok.slice(-6),
        vendeg_atadas_azonosito: vendegAtadas?.azonosito || null,
      }),
    })
      .then((valasz) => (valasz.ok ? valasz.json() : null))
      .then((adat) => {
        // FLOW SOSEM MARADHAT NÉMA BELÉPÉS UTÁN.
        //
        // Korábban az üres válasz és a hiba is csendet jelentett: a
        // felhasználó belépett, és nem történt semmi. Google-belépésnél ez
        // ténylegesen előfordult. A szerveroldali tartalék nem segít, ha a
        // kérés el sem jut odáig, ezért itt is kell egy.
        //
        // A TARTALÉKSZÖVEG CSAK A SZÖVEGET PÓTOLJA -- A NÉVKÉRDÉST NEM.
        //
        // Eddig a tartalék egy önálló üzenet volt, `nevetKer` és
        // `nevJavaslatok` nélkül. Így amikor a szerver válaszolt, de üres
        // üzenettel, a válasz többi mezője a földre esett: a megszólítást
        // kérő kérdés és a névjavaslat-gombok sem jelentek meg. Mérve
        // (2026-07-30): pontosan ez történt, ezért nem szólított néven, és
        // nem is kérdezte meg, hogyan szólítsa.
        //
        // Ha a szerver válaszolt, a mezőit megtartjuk, és csak a szöveget
        // pótoljuk. Ha egyáltalán nem válaszolt (`adat` null), nincs mit
        // megtartani -- olyankor nem találgatunk: a megszólítás állapotát
        // csak a szerver tudja, és rosszul kérdezni rosszabb, mint nem
        // kérdezni.
        if (
          ["atadva", "mar_atadva"].includes(adat?.vendeg_atadas_allapot)
        ) {
          window.localStorage.removeItem(VENDEG_CHAT_KULCS);
          vendegElozmenyRef.current = [];
        }
        celValasztasRef.current = adat?.valasz_tipus === "celmunkakor";
        celSzabadMegadasRef.current =
          adat?.valasz_tipus === "celmunkakor" &&
          !(adat?.valaszlehetosegek || []).length;
        if (adat?.active_view === "cv_feltoltes") {
          kezdoValasztasRef.current = "cv";
          setKezdoValasztas("cv");
        } else if (adat?.active_view === "cv_cel") {
          kezdoValasztasRef.current = "cv-cel";
          setKezdoValasztas("cv-cel");
        }
        setUzenetek(belepesUzenetek(adat));
      })
      .catch(() => {
        // Az átadandó vendégbeszélgetést hiba esetén NEM töröljük.
        setUzenetek([{ ...tartalekKoszontes(), gepel: true }]);
      })
      .finally(() => setKuldesFolyamatban(false)),
    );
  }, [felhasznaloId]);

  useEffect(() => {
    if (!session || folytatasRef.current || kuldesFolyamatban) return;

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

    kezdoLepesValasztasa(KEZDO_LEPESEK[0]).then((sikerult) => {
      if (!sikerult) return;
      folytatasRef.current = true;
      window.localStorage.removeItem("career_pending_start");
    });
  }, [session, kuldesFolyamatban]);

  // A „Van CV-m" után nem a hosszú Flow-panel tetejére, hanem közvetlenül
  // az újonnan megjelent feltöltőre görgetünk. A korábbi általános
  // panelgörgetés pont a friss tartalmat vitte a képernyő alá.
  useEffect(() => {
    if (elsoRenderRef.current) {
      elsoRenderRef.current = false;
      return;
    }
    if (kezdoValasztas !== "cv" || cvMuvelet) return;
    const frame = window.requestAnimationFrame(() => {
      cvFeltoltesRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [kezdoValasztas, cvMuvelet]);

  // Új üzenetnél a beszélgetés aljára: enélkül Flow válasza a látható
  // terület fölött jelenik meg, és úgy tűnik, mintha semmi nem történt volna.
  useEffect(() => {
    if (uzenetek.length <= 1) return;
    // `nearest`: csak annyit görget, amennyi tényleg kell. A `end` mindig
    // az aljára rántotta a nézetet, ettől ugrott egyet az oldal küldéskor.
    uzenetVegeRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
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

  // A belépő/regisztrációs oldalra indulás EGYETLEN útja. A jelzőt itt
  // tesszük le, mert pontosan egy esetben nem szabad Flow-nak újra
  // bemutatkoznia: ha a látogató elolvasta a köszöntőt, elindult
  // regisztrálni vagy belépni, de nem fejezte be, és visszajött.
  //
  // Minden más eset marad a régiben: friss látogató végignézi a
  // bemutatkozást, ahogy eddig.
  function loginraNavigalas(url = "/login?next=%2F") {
    if (!belepve) vendegAtadasMentese(uzenetek);
    window.sessionStorage.setItem("career_login_probalkozas", "1");
    router.push(url);
  }

  // Vendégként a saját belépőoldalra visszük. A választás a böngészőben
  // marad, és belépés után onnan folytatjuk.
  function belepesreKuldes(megorzendo) {
    for (const [kulcs, ertek] of Object.entries(megorzendo)) {
      window.localStorage.setItem(kulcs, ertek);
    }
    loginraNavigalas();
  }

  async function kezdoLepesValasztasa(lepes) {
    if (kezdoValasztasRef.current || kuldesFolyamatban) return false;

    if (!belepve) {
      belepesreKuldes(
        lepes.id === "cv"
          ? { career_pending_start: "cv" }
          : { career_pending_message: lepes.cim },
      );
      return false;
    }

    if (lepes.id === "cv") {
      // Ez még nem elemzési szándék, de már aktív munkafolyamat. Előbb
      // szerverre mentjük, így F5 után ugyanitt nyílik vissza.
      setKuldesFolyamatban(true);
      setHiba(null);
      try {
        const valasz = await apiFetch("/api/v1/flow/kezdes", {
          method: "POST",
          body: JSON.stringify({ utvonal: "cv" }),
        });
        if (!valasz.ok) throw new Error(`flow-kezdes: ${valasz.status}`);
        const adat = await valasz.json();
        kezdoValasztasRef.current = lepes.id;
        setKezdoValasztas(lepes.id);
        setUzenetek((elozo) => [
          ...elozo,
          { szerep: "user", szoveg: lepes.cim },
          { szerep: "flow", szoveg: adat.uzenet },
        ]);
        return true;
      } catch {
        setHiba("A CV-folyamat indítása nem sikerült. Próbáld újra.");
        return false;
      } finally {
        setKuldesFolyamatban(false);
      }
    }
    kezdoValasztasRef.current = lepes.id;
    setKezdoValasztas(lepes.id);
    uzenetKuldese(lepes.cim);
    return true;
  }

  function cvJovahagyasKesz(eredmeny) {
    kezdoValasztasRef.current = "cv-cel";
    setKezdoValasztas("cv-cel");

    // AMIT MÁR MEGERŐSÍTETT, AZT NE KÉRDEZZÜK MEG ÚJRA.
    //
    // Ez az ág eddig hiányzott: a CV-jóváhagyás után Flow MINDIG rákérdezett a
    // célmunkakörre, akkor is, ha a felhasználó azt korábban már megerősítette.
    // A spec (3. fejezet első sora és 11.4) ezt kifejezetten tiltja: ilyenkor
    // meg kell MUTATNI a célt, és csak egy „Módosítom" lehetőséget adni
    // mellé -- kérdés nélkül.
    if (megerositettCel) {
      celValasztasRef.current = false;
      celSzabadMegadasRef.current = false;
      setUzenetek((elozo) => [
        ...elozo,
        {
          szerep: "flow",
          szoveg:
            `A CV-d rendben megérkezett. A célod: ${megerositettCel} — ` +
            "ezzel dolgozom tovább.",
          valaszlehetosegek: ["Módosítom"],
        },
      ]);
      setWorkflowState(eredmeny.current_state || workflowState);
      setValaszthatoLepesek(eredmeny.available_actions || []);
      gpsFrissites();
      return;
    }

    const valaszlehetosegek =
      eredmeny.flow_valaszlehetosegek ||
      (eredmeny.celmunkakor_javaslatok || [])
        .slice(0, 1)
        .map((sor) => sor.szakma)
        .concat(["Másra készülök"]);
    celValasztasRef.current = valaszlehetosegek.length > 0;
    celSzabadMegadasRef.current = valaszlehetosegek.length === 0;
    setUzenetek((elozo) => [
      ...elozo,
      {
        szerep: "flow",
        szoveg:
          eredmeny.flow_uzenet ||
          "A CV-d rendben megérkezett. Milyen pozíció vagy szakma a célod?",
        valaszlehetosegek,
      },
    ]);
    setWorkflowState(eredmeny.current_state || workflowState);
    setValaszthatoLepesek(eredmeny.available_actions || []);
    gpsFrissites();
  }

  async function celmunkakorMentese(celmunkakor) {
    const tisztaCel = celmunkakor.trim();
    if (!tisztaCel || kuldesFolyamatban) return;
    setHiba(null);
    setKuldesFolyamatban(true);
    setUzenetek((elozo) => [
      ...elozo,
      { szerep: "user", szoveg: tisztaCel },
    ]);
    setSzoveg("");
    try {
      const valasz = await apiFetch("/api/v1/flow/celmunkakor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_role: tisztaCel }),
      });
      if (!valasz.ok) throw new Error(`flow-celmunkakor: ${valasz.status}`);
      const adat = await valasz.json();
      celValasztasRef.current = false;
      celSzabadMegadasRef.current = false;
      // Mostantól ez a megerősített cél. Enélkül egy F5 nélküli, ugyanabban a
      // munkamenetben történő újabb CV-feltöltés megint rákérdezne rá.
      setMegerositettCel(tisztaCel);
      setUzenetek((elozo) => [
        ...elozo,
        {
          szerep: "flow",
          szoveg: adat.uzenet,
          valaszlehetosegek: adat.valaszlehetosegek || [],
        },
      ]);
      setWorkflowState(adat.current_state || workflowState);
      setValaszthatoLepesek(adat.available_actions || []);
      gpsFrissites();
    } catch {
      setHiba("A célmunkakör mentése nem sikerült. Próbáld újra.");
    } finally {
      setKuldesFolyamatban(false);
    }
  }

  function flowValaszKivalasztasa(valasz) {
    const kezdoLepes = KEZDO_LEPESEK.find((lepes) => lepes.cim === valasz);
    if (kezdoLepes && !kezdoValasztasRef.current) {
      kezdoLepesValasztasa(kezdoLepes);
      return;
    }
    // „Módosítom": a megmutatott célt mégis átírná. Ez nem ismételt kérdés,
    // hanem az ő kezdeményezése -- a spec 3. fejezete pont ezt a lehetőséget
    // írja elő a megerősített cél mellé.
    if (valasz === "Módosítom") {
      celValasztasRef.current = false;
      celSzabadMegadasRef.current = true;
      setUzenetek((elozo) => [
        ...elozo,
        { szerep: "user", szoveg: valasz },
        {
          szerep: "flow",
          szoveg: "Rendben. Milyen pozíció vagy szakma legyen a cél?",
        },
      ]);
      return;
    }
    if (celValasztasRef.current) {
      if (valasz === "Másra készülök") {
        celValasztasRef.current = false;
        celSzabadMegadasRef.current = true;
        setUzenetek((elozo) => [
          ...elozo,
          { szerep: "user", szoveg: valasz },
          {
            szerep: "flow",
            szoveg: "Rendben. Milyen pozíció vagy szakma a célod?",
          },
        ]);
        return;
      }
      celmunkakorMentese(valasz);
      return;
    }
    if (valasz === "Nézd át a CV-met") {
      cvMuveletValasztasa(CV_ELLENORZES_MUVELET);
      return;
    }
    if (valasz === "Mutasd a piacot") {
      cvMuveletValasztasa(PIAC_MUVELET);
      return;
    }
    uzenetKuldese(valasz);
  }

  async function cvMuveletValasztasa(muvelet) {
    if (cvMuvelet || kuldesFolyamatban) return;
    setHiba(null);
    setFutoMuvelet(muvelet.id);
    setKuldesFolyamatban(true);
    setUzenetek((elozo) => [
      ...elozo,
      { szerep: "user", szoveg: muvelet.kerdes },
    ]);

    try {
      const valasz = await apiFetch("/api/v1/workflow/intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent: muvelet.intent }),
      });
      if (!valasz.ok) throw new Error(`workflow-intent: ${valasz.status}`);
      const dontes = await valasz.json();
      setCvMuvelet(muvelet.id);
      if (muvelet.id === "piac") {
        kezdoValasztasRef.current = "piac";
        setKezdoValasztas("piac");
      }
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
    if (belepve && kezdoValasztas) {
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
    celValasztasRef.current = false;
    celSzabadMegadasRef.current = false;
    setUzenetek(belepve ? [] : [VENDEG_UZENET]);
    setSzoveg("");
    setHiba(null);
    gpsFrissites();

    if (!belepve) {
      setKuldesFolyamatban(false);
      return;
    }

    // Belépve nincs mire visszaesni: friss beszélgetéshez Flow ugyanúgy
    // köszönt, mint belépéskor -- csak vendégelőzmény nélkül.
    try {
      const valasz = await apiFetch("/api/v1/flow/belepes-utan", {
        method: "POST",
        body: JSON.stringify({ vendeg_elozmeny: [] }),
      });
      const adat = valasz.ok ? await valasz.json() : null;
      if (adat?.uzenet) {
        celValasztasRef.current = adat.valasz_tipus === "celmunkakor";
        celSzabadMegadasRef.current =
          adat.valasz_tipus === "celmunkakor" &&
          !(adat.valaszlehetosegek || []).length;
        setUzenetek([koszontoUzenet(adat)]);
      }
    } catch {
      // Köszöntés nélkül is használható a beszélgetés.
    } finally {
      setKuldesFolyamatban(false);
    }
  }

  async function uzenetKuldese(uzenetSzoveg) {
    const tiszta = uzenetSzoveg.trim();
    if (!tiszta || kuldesFolyamatban) return;

    if (belepve && celSzabadMegadasRef.current) {
      await celmunkakorMentese(tiszta);
      return;
    }

    if (!belepve) {
      // Vendégmód: szűk hatókörű, bejelentkezés nélküli Flow-válasz.
      // Nincs profil, nincs előzmény, nincs állapotgép -- a szerver
      // prompt korlátozza, mit mondhat, és IP-alapú keret védi.
      setHiba(null);
      setUzenetek((elozo) => [...elozo, { szerep: "user", szoveg: tiszta }]);
      setSzoveg("");
      setKuldesFolyamatban(true);
      try {
        // Vendégmódban nincs szerveroldali előzmény, ezért a kliens küldi
        // az utolsó néhány üzenetet. A szerver korlátozza a hosszát, és
        // adatként kezeli, nem utasításként.
        const valasz = await publicApiFetch("/api/v1/flow/guest-messages", {
          method: "POST",
          body: JSON.stringify({
            kerdes: tiszta,
            elozmenyek: uzenetek.slice(-6).map((uzenet) => ({
              szerep: uzenet.szerep,
              szoveg: uzenet.szoveg.slice(0, 600),
            })),
          }),
        });
        if (!valasz.ok) throw new Error(`flow-guest: ${valasz.status}`);
        const adat = await valasz.json();
        setUzenetek((elozo) => [
          ...elozo,
          { szerep: "flow", szoveg: adat.valasz || "", gepel: true },
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
          // Csak a belépés utáni ELSŐ üzenetnél megy át, és a szerver sem
          // menti el -- kizárólag ehhez az egy válaszhoz ad kontextust.
          vendeg_elozmeny: vendegElozmenyRef.current,
          app_ismeret:
            "A Karrier-Ügynökség ellenőrzött karrierprofilt, Career GPS-t, " +
            "piaci körképet, állásillesztést és pályázati anyagokat készít.",
        }),
      });
      if (!valasz.ok) throw new Error(`flow-messages: ${valasz.status}`);
      vendegElozmenyRef.current = [];
      const dontes = await valasz.json();

      setUzenetek((elozo) => [
        ...elozo,
        {
          szerep: "flow",
          szoveg: dontes.response_message || "",
          // Ha Flow a nevet kéri, alatta egy apró mező jelenik meg. A nevet
          // szándékosan nem a modell nyeri ki a mondatból: azt beírod, és
          // úgy kerül a profilba.
          nevetKer: (dontes.required_fields || []).includes("display_name"),
          // Ha Flow nemcsak beszélt, hanem le is futtatott egy modult, az
          // eredménye itt, a válasza alatt jelenik meg.
          akcio: dontes.accepted_action || null,
          eredmeny: dontes.eredmeny || null,
          muveletHiba: dontes.muvelet_hiba || null,
          // A karriercél rögzítése a te döntésed, nem Flow-é: ő csak
          // visszakérdez, a pipa a rábólintásod után kerül ki.
          megerositendoIntent: dontes.megerositendo_intent || null,
          // Flow saját kérdéséhez tartozó válaszgombok. Ezek helyettesítik
          // az állandó kártyarácsot: nem menü, hanem egy kérdés válaszai.
          valaszlehetosegek: dontes.valaszlehetosegek || [],
        },
      ]);
      setValaszthatoLepesek(dontes.available_actions || []);
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

      {/* VENDÉGKÉNT NEM A 0%-OT MUTATJUK.
          Egy látogatónak a „0% készültség" és az öt lezárt lépés azt üzeni,
          hogy itt még nem csinálhat semmit. Nem eladja az oldalt, hanem
          elveszi a kedvét. Helyette azt mondjuk el, MI FOG történni. */}
      {belepve ? (
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
      ) : (
        <div className="mb-6 rounded-2xl border border-amber-300/15 bg-amber-300/[0.04] p-4">
          <p className="text-xs font-semibold text-amber-200">
            Így fog kinézni az utad
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            Öt lépés, ebben a sorrendben. Mindegyik akkor lép tovább, ha
            tényleg elkészült valami — nem becsülünk találomra.
          </p>
        </div>
      )}

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

  // Amíg a böngészőből nem olvastuk ki a Supabase-munkamenetet, nem
  // rajzolunk vendégfelületet. Korábban néhány pillanatra (lassabb gépen
  // jóval tovább) vendégnek látszott a már belépett felhasználó, majd a
  // teljes oldal átváltott alatta.
  if (session === undefined) {
    return (
      <main className="career-shell career-grid grid min-h-screen place-items-center">
        <div
          role="status"
          aria-live="polite"
          className="glass-panel flex items-center gap-3 rounded-2xl px-5 py-4 text-sm text-slate-300"
        >
          <span className="flow-pulse h-2.5 w-2.5 rounded-full bg-amber-300" />
          Flow betölti a munkameneted…
        </div>
      </main>
    );
  }

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
                <div className="flex items-center gap-3">
                  {belepve && kezdoValasztas && (
                    <button
                      type="button"
                      onClick={kezdoAllapotVisszaallitasa}
                      disabled={kuldesFolyamatban}
                      className="text-[11px] font-semibold text-slate-400 hover:text-amber-100 disabled:opacity-40"
                    >
                      Másik út választása
                    </button>
                  )}
                  <span className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-emerald-200/80">
                    elérhető
                  </span>
                </div>
              </div>

                <div className="space-y-4 p-5 sm:p-6">
                  {uzenetek.map((uzenet, index) => (
                    <div
                      key={`${uzenet.szerep}-${index}`}
                      /* whitespace-pre-line: a többbekezdéses üzenetek
                         (pl. a vendégköszöntő) különben egyetlen tömbbé
                         folynának össze. */
                      className={`max-w-[92%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-6 sm:max-w-[82%] ${
                        uzenet.szerep === "flow"
                          ? "border border-amber-300/12 bg-amber-300/[0.05] text-slate-200"
                          : "ml-auto border-2 border-amber-300/80 bg-slate-900/70 text-white"
                      }`}
                    >
                      {uzenet.gepel ? (
                        <GepeloSzoveg
                          szoveg={uzenet.szoveg}
                          sebessegMs={uzenet.gepelSebesseg}
                          maxIdotartamMs={uzenet.gepelMaxIdotartamMs}
                        />
                      ) : (
                        uzenet.szoveg
                      )}
                      {uzenet.celRogzitve && (
                        <p className="mt-2 text-xs text-emerald-200/80">
                          Cél rögzítve.
                        </p>
                      )}
                      {uzenet.nevMentve && (
                        <p className="mt-2 text-xs text-emerald-200/80">
                          Elmentve: {uzenet.nevMentve}
                        </p>
                      )}
                      {uzenet.eredmeny && (
                        <div className="mt-3 rounded-xl border border-white/8 bg-black/25 p-4">
                          <FlowEredmeny
                            action={uzenet.akcio}
                            adat={uzenet.eredmeny}
                          />
                        </div>
                      )}
                      {uzenet.muveletHiba && (
                        <p className="mt-3 rounded-xl border border-amber-300/25 bg-amber-300/[0.07] px-3.5 py-2.5 text-xs leading-5 text-amber-100">
                          {uzenet.muveletHiba}
                        </p>
                      )}

                      {/* FLOW KÉRDEZ, ÉS ITT VANNAK A VÁLASZOK.
                          Ez helyettesíti az állandó kártyarácsot: nem menü,
                          hanem egy kérdés lehetséges válaszai. Csak a LEGUTOLSÓ
                          üzenetnél jelennek meg -- a korábbi kérdésekre már
                          válaszoltál, azok gombjai csak zavarnának.
                          A kezdő- és célválaszok profilt építenek; a két
                          szolgáltatásgomb csak az ellenőrzött backend-kaput
                          indítja. A szabad szöveg is marad. */}
                      {(uzenet.valaszlehetosegek || []).length > 0 &&
                        index === uzenetek.length - 1 &&
                        !kuldesFolyamatban && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {uzenet.valaszlehetosegek.map((valasz) => (
                              <button
                                key={valasz}
                                type="button"
                                onClick={() => flowValaszKivalasztasa(valasz)}
                                className="rounded-full border border-amber-300/30 bg-amber-300/[0.07] px-4 py-1.5 text-xs font-semibold text-amber-100 hover:border-amber-300/60 hover:bg-amber-300/15"
                              >
                                {valasz}
                              </button>
                            ))}
                          </div>
                        )}
                      {belepve &&
                        uzenet.nevetKer &&
                        index === uzenetek.length - 1 && (
                          <MegszolitasMezo
                            javaslatok={uzenet.nevJavaslatok || []}
                            onKesz={(nev) =>
                              // Flow üzenetét NEM írjuk át: ha hozzáfűznénk
                              // a visszaigazolást, úgy tűnne, mintha
                              // megismételné magát. Csak a mező helyére
                              // kerül egy rövid nyugta.
                              setUzenetek((elozo) =>
                                elozo.map((sor, i) =>
                                  i === elozo.length - 1
                                    ? { ...sor, nevetKer: false, nevMentve: nev }
                                    : sor,
                                ),
                              )
                            }
                          />
                        )}
                      {!belepve &&
                        uzenet.szerep === "flow" &&
                        index === uzenetek.length - 1 && (
                          <span className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => loginraNavigalas()}
                              className="rounded-full border border-amber-300/50 px-4 py-1.5 text-xs font-semibold text-amber-100 hover:border-amber-200 hover:bg-amber-300/10"
                            >
                              Belépés
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                loginraNavigalas("/login?next=%2F&mod=regisztracio")
                              }
                              className="rounded-full bg-amber-300 px-4 py-1.5 text-xs font-bold text-slate-950 hover:bg-amber-200"
                            >
                              Regisztráció
                            </button>
                          </span>
                        )}
                    </div>
                  ))}
                  {kuldesFolyamatban && (
                    <div className="flex max-w-[82%] items-center gap-2.5 rounded-2xl border border-amber-300/12 bg-amber-300/[0.05] px-4 py-3 text-sm text-slate-400">
                      <span className="flow-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                      Flow feldolgozza a következő lépést…
                    </div>
                  )}
                  {/* A panelek a beszélgetésen BELÜL jelennek meg, Flow
                      üzenete alatt -- nem cserélik le a chatet. Így ő vezet,
                      a panelek pedig a válaszlehetőségei. */}
                  {belepve && kezdoValasztas === "cv" && !cvMuvelet && (
                    <div ref={cvFeltoltesRef} className="scroll-mt-24">
                      <ProfileGate
                        embedded
                        forceCvUpload
                        onStateChange={cvJovahagyasKesz}
                      />
                    </div>
                  )}

                  {/* NEM NYÍLHAT MEG KÉT PROFILPANEL EGYSZERRE.
                      Ennek a feltétele eddig csak a `workflowState`-et nézte,
                      a fenti CV-feltöltésé meg csak a `kezdoValasztas`-t --
                      így egy visszatérő felhasználónál, akinek már
                      `CEL_TISZTAZOTT` az állapota, a „Van CV-m" után MINDKETTŐ
                      megjelent. Két feltöltési felület egyszerre pontosan az,
                      amit a spec 11.1 tilt. */}
                  {belepve &&
                    !cvFolyamatAktiv &&
                    [
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
                          setValaszthatoLepesek(result.available_actions || []);
                          gpsFrissites();
                        }}
                      />
                    )}

                  {belepve && valaszthatoLepesek.length > 0 && (
                    <FolyamatPanel
                      availableActions={valaszthatoLepesek}
                      // EGY KÁRTYA EGY ZÁRT FOLYAMAT.
                      //
                      // Eddig csak a `"cv"` fázisra szűkült a panel. A
                      // CV-jóváhagyás után viszont az állapot `"cv-cel"`-re
                      // vált, és ettől a szűkítés megszűnt: a célmunkakör
                      // megadása közben újra kinyílt az álláskeresés és a
                      // piaci körkép is. A spec 2.7 szerint a CV-feltöltés
                      // után nincs újabb szolgáltatásválasztás -- a lánc fut.
                      aktivFolyamat={cvFolyamatAktiv ? "cv" : null}
                      onStateChange={(result) => {
                        setWorkflowState(result.current_state);
                        setValaszthatoLepesek(result.available_actions || []);
                        gpsFrissites();
                      }}
                    />
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
                      placeholder="Írd le néhány mondatban, hol tartasz és miben segítsek…"
                      rows={2}
                      maxLength={4000}
                      className="w-full resize-y rounded-2xl border border-amber-300/40 bg-slate-950/70 px-5 pb-12 pt-4 text-sm leading-6 text-white placeholder:text-slate-500 focus:border-amber-300/70 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                    />
                    <div className="pointer-events-none absolute bottom-4 left-5 text-[11px] text-slate-600">
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

                </div>
            </div>

            {hiba && (
              <div className="mt-4 rounded-2xl border border-red-300/20 bg-red-300/[0.06] px-4 py-3 text-sm text-red-100">
                {hiba}
              </div>
            )}

            {/* A kirakat csak vendégként látszik. Belépve Flow vezet, ott egy
                hétfelé ágazó menü csak elvenné a figyelmet a beszélgetésről. */}
            {!belepve && (
            <section className="mt-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-200">
                  Amiben segítek
                </h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
                    <p className="mt-2 text-[11px] leading-4 text-slate-400">
                      {modul.allapot}
                    </p>
                  </article>
                ))}
              </div>
            </section>
            )}
          </section>

          <div className="hidden lg:block">{gpsPanel}</div>
        </div>
      </div>
    </main>
  );
}
