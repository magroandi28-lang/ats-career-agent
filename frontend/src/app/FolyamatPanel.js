"use client";

import { useState } from "react";
import { apiFetch } from "../lib/api";

// A kulcsok a backend CareerAction értékei. Csak azok jelennek meg, amiket
// a szerver az `available_actions` listában ténylegesen felkínál -- így a
// felület sosem ajánl olyan lépést, ami 501-be futna.
const AKCIO_FELIRATOK = {
  piaci_korkep_inditasa: {
    cim: "Piaci körkép",
    leiras:
      "Kereslet, bér és átjárhatóság a saját adatainkból — kérdésenként " +
      "megjelölve, mennyire megbízható.",
  },
  allaskereses_inditasa: {
    cim: "Álláskeresés indítása",
    leiras: "Előbb megmutatjuk, milyen feltételekkel fogunk keresni.",
  },
  allasok_bemutatasa: {
    cim: "Találatok megmutatása",
    leiras: "Legfeljebb öt megfelelő állás, illeszkedés szerint rangsorolva.",
  },
  cv_ellenorzes_inditasa: {
    cim: "CV új változata",
    leiras: "Az eredeti CV mellé elkészül a szerkeszthető új változat.",
  },
  cv_frissites_inditasa: {
    cim: "CV új változata",
    leiras:
      "Az eredeti mellé elkészítjük a célmunkakörhöz igazított, " +
      "szerkeszthető új változatot.",
  },
  cv_keszites_inditasa: {
    cim: "CV készítése",
    leiras: "Igazolt tényekből, nulláról.",
  },
  tanacsadas_inditasa: {
    cim: "Tanácsadás",
    leiras: "Döntési helyzet átbeszélése forrásolt anyagokból.",
  },
};

// A bizalmi szint KÉRDÉSENKÉNT külön jár. Egy szakmáról tudhatjuk pontosan,
// hány állás van, miközben a béréről semmit -- egyetlen közös jelző ezt
// elmosná, és a felhasználó nem tudná, mire támaszkodhat.
const BIZALOM_FELIRAT = {
  eros: { szoveg: "erős adat", szin: "text-emerald-300" },
  gyenge: { szoveg: "kevés adat", szin: "text-amber-300" },
  nincs: { szoveg: "nincs adat", szin: "text-slate-500" },
};

function Bizalom({ cimke, szint }) {
  const jel = BIZALOM_FELIRAT[szint];
  if (!jel) return null;
  return (
    <span className="text-xs text-slate-400">
      {cimke}: <span className={jel.szin}>{jel.szoveg}</span>
    </span>
  );
}

function Forint({ ertek }) {
  if (ertek == null) return null;
  return <>{Number(ertek).toLocaleString("hu-HU")} Ft</>;
}

function PiaciKorkep({ adat }) {
  const ber = adat.ber || {};
  const bizalom = adat.bizalom || {};
  const atjarhatosag = adat.atjarhatosag || [];
  const leiras = adat.esco?.[0]?.leiras;

  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h4 className="text-base font-semibold text-white">{adat.szakma}</h4>
        {adat.kereslet?.kategoria && (
          <span className="text-xs text-amber-200">{adat.kereslet.kategoria}</span>
        )}
      </div>

      <p className="mt-2 text-sm text-slate-300">
        {Number(adat.hirdetesek_szama).toLocaleString("hu-HU")} hirdetés
        {adat.cegek_szama > 0 && <> · {adat.cegek_szama} cégtől</>}
        {adat.kereslet?.friss_30 != null && (
          <> · {adat.kereslet.friss_30} az elmúlt 30 napban</>
        )}
      </p>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <Bizalom cimke="Kereslet" szint={bizalom.kereslet} />
        <Bizalom cimke="Bér" szint={bizalom.ber} />
        <Bizalom cimke="Elvárások" szint={bizalom.elvaras} />
      </div>

      {(ber.hirdetett_median != null || ber.ksh_atlagkereset != null) && (
        <div className="mt-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Bér
          </p>
          {ber.hirdetett_median != null && (
            <p className="mt-1.5 text-sm text-slate-200">
              Hirdetett medián: <Forint ertek={ber.hirdetett_median} />
              {ber.hirdetett_mintaszam > 0 && (
                <span className="text-xs text-slate-500">
                  {" "}
                  ({ber.hirdetett_mintaszam} hirdetésből)
                </span>
              )}
            </p>
          )}
          {ber.ksh_atlagkereset != null && (
            <p className="mt-1 text-sm text-slate-200">
              KSH-átlagkereset: <Forint ertek={ber.ksh_atlagkereset} />
              {ber.ksh_idoszak && (
                <span className="text-xs text-slate-500"> ({ber.ksh_idoszak})</span>
              )}
            </p>
          )}
          {ber.figyelmeztetes && (
            <p className="mt-1.5 text-xs leading-5 text-amber-200/80">
              {ber.figyelmeztetes}
            </p>
          )}
        </div>
      )}

      {atjarhatosag.length > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Ide vihető át a tudásod
          </p>
          <ul className="mt-2 space-y-1.5">
            {atjarhatosag.map((szomszed) => (
              <li
                key={szomszed.szakma}
                className="flex items-center justify-between gap-4 text-sm"
              >
                <span className="text-slate-200">{szomszed.szakma}</span>
                <span className="shrink-0 text-xs text-slate-500">
                  {szomszed.kozos_keszseg} közös készség
                  {szomszed.allas > 0 && ` · ${szomszed.allas} állás`}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Közös készségek alapján, az ESCO szakmaleírásaiból. Lehetőség, nem
            javaslat — te döntesz.
          </p>
        </div>
      )}

      {leiras && (
        <p className="mt-4 text-xs leading-5 text-slate-400">{leiras}</p>
      )}
    </div>
  );
}

function Allaslista({ adat }) {
  if (!adat.talalatok_szama) {
    return (
      <div>
        <p className="text-sm text-slate-200">
          Ezekkel a feltételekkel most nincs olyan találat, amit jó szívvel
          ajánlanánk.
        </p>
        {adat.piaci_jelzes && (
          <p className="mt-2 text-xs leading-5 text-slate-400">
            Piaci jelzés: {adat.piaci_jelzes}
          </p>
        )}
      </div>
    );
  }

  return (
    <div>
      <p className="text-sm text-slate-300">
        {adat.talalatok_szama} megfelelő találat · {adat.szakma} ·{" "}
        {adat.helyszin}
      </p>
      <ul className="mt-3 space-y-2.5">
        {adat.allasok.map((allas, index) => (
          <li
            key={allas.link || `${allas.cim}-${index}`}
            className="rounded-xl border border-white/8 bg-black/15 p-3.5"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="text-sm font-semibold text-slate-100">
                {allas.cim}
              </span>
              {allas.illeszkedes != null && (
                <span className="shrink-0 text-xs font-semibold text-amber-200">
                  {allas.illeszkedes}% illeszkedés
                </span>
              )}
            </div>
            {allas.ceg && (
              <p className="mt-1 text-xs text-slate-400">
                {allas.ceg}
                {allas.helyszin && ` · ${allas.helyszin}`}
                {allas.datum && ` · ${allas.datum}`}
              </p>
            )}
            {allas.link && (
              <a
                href={allas.link}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-xs font-semibold text-amber-200 hover:text-amber-100"
              >
                Eredeti hirdetés megnyitása →
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function KeresesiFeltetelek({ adat }) {
  return (
    <div>
      <p className="text-sm text-slate-200">
        Ezekkel a feltételekkel fogunk keresni:
      </p>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-slate-500">Célmunkakör</dt>
          <dd className="text-slate-200">{adat.szakma}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Helyszín</dt>
          <dd className="text-slate-200">{adat.helyszin}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-slate-500">Figyelembe vett készségek</dt>
          <dd className="text-slate-200">{adat.keszsegek.join(", ")}</dd>
        </div>
      </dl>
    </div>
  );
}

function CvUjValtozat({ adat }) {
  const [editedCv, setEditedCv] = useState(adat.improved_cv || "");
  const [copied, setCopied] = useState(false);
  const userEdited = editedCv !== (adat.improved_cv || "");

  async function copyCv() {
    await navigator.clipboard.writeText(editedCv);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div>
      <h4 className="text-base font-semibold text-white">
        Elkészült a CV új változata
      </h4>
      <p className="mt-1.5 text-xs leading-5 text-slate-400">
        Célmunkakör: {adat.target_role}. Az új szöveg csak a feltöltött
        CV-ben szereplő tényeket használja.
      </p>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <section>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Eredeti
          </p>
          <pre className="min-h-96 max-h-[42rem] overflow-auto whitespace-pre-wrap rounded-xl border border-white/8 bg-slate-950/60 p-4 font-sans text-xs leading-5 text-slate-400">
            {adat.original_cv}
          </pre>
        </section>

        <section>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-200/80">
            Új, szerkeszthető változat
          </p>
          <textarea
            value={editedCv}
            onChange={(event) => setEditedCv(event.target.value)}
            rows={24}
            maxLength={120000}
            className="min-h-96 max-h-[42rem] w-full resize-y rounded-xl border border-amber-300/25 bg-slate-950/70 p-4 text-sm leading-6 text-slate-100 focus:border-amber-300/60"
          />
        </section>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p
          className={`text-xs ${
            userEdited ? "text-amber-200/80" : "text-emerald-200/80"
          }`}
        >
          {userEdited
            ? "Saját szerkesztés — a módosításokat még nem ellenőriztük"
            : "Tényellenőrzés rendben"}
        </p>
        <button
          type="button"
          onClick={copyCv}
          disabled={!editedCv.trim()}
          className="rounded-xl border border-amber-300/35 px-4 py-2 text-xs font-semibold text-amber-100 hover:bg-amber-300/10 disabled:opacity-50"
        >
          {copied ? "Kimásolva" : "Új változat másolása"}
        </button>
      </div>
    </div>
  );
}

/** Ugyanaz a megjelenítés a gombos indításnál és Flow válaszánál -- két
 *  külön változat óhatatlanul elcsúszna egymástól. */
export function Eredmeny({ action, adat }) {
  if (!adat) return null;
  if (
    action === "cv_ellenorzes_inditasa" ||
    action === "cv_frissites_inditasa"
  ) {
    return <CvUjValtozat adat={adat} />;
  }
  if (action === "piaci_korkep_inditasa") return <PiaciKorkep adat={adat} />;
  if (action === "allasok_bemutatasa") return <Allaslista adat={adat} />;
  if (action === "allaskereses_inditasa") {
    return <KeresesiFeltetelek adat={adat} />;
  }
  return null;
}

// EGY KÁRTYA EGY FOLYAMAT.
//
// A szerver minden olyan lépést felkínál, ami az adott állapotból
// engedélyezett -- CV-átvizsgálás közben az álláskeresést és a piaci
// körképet is. Ettől a folyamat szétesett: a felhasználó a CV-nél tartott,
// és három egymástól független út nyílt meg előtte egyszerre.
//
// Itt szűkítünk arra, ami az ÉPPEN VÁLASZTOTT folyamathoz tartozik. A többi
// nem tűnik el véglegesen: az adott folyamat lezárása után újra elérhető.
const FOLYAMAT_LEPESEI = {
  cv: [
    "cv_ellenorzes_inditasa",
    "cv_frissites_inditasa",
    "cv_keszites_inditasa",
  ],
  allas: ["allaskereses_inditasa", "allasok_bemutatasa"],
  piac: ["piaci_korkep_inditasa"],
  tanacs: ["tanacsadas_inditasa"],
};

export default function FolyamatPanel({
  availableActions = [],
  aktivFolyamat = null,
  onStateChange,
}) {
  const [futo, setFuto] = useState(null);
  const [eredmeny, setEredmeny] = useState(null);
  const [hiba, setHiba] = useState(null);

  const engedett = FOLYAMAT_LEPESEI[aktivFolyamat] || null;
  const lepesek = availableActions
    .filter((akcio) => AKCIO_FELIRATOK[akcio])
    .filter((akcio) => !engedett || engedett.includes(akcio));

  async function inditas(action) {
    if (futo) return;
    setFuto(action);
    setHiba(null);
    try {
      const valasz = await apiFetch("/api/v1/workflow/action", {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      if (!valasz.ok) {
        let uzenet = "A lépés indítása nem sikerült.";
        try {
          const test = await valasz.json();
          if (test.detail) uzenet = test.detail;
        } catch {
          // Marad az általános üzenet.
        }
        throw new Error(uzenet);
      }
      const test = await valasz.json();
      setEredmeny({ action, adat: test.result });
      onStateChange?.(test);
    } catch (lepesHiba) {
      setHiba(lepesHiba.message || "A lépés indítása nem sikerült.");
    } finally {
      setFuto(null);
    }
  }

  if (!lepesek.length && !eredmeny) return null;

  return (
    <section className="mt-6">
      {lepesek.length > 0 && (
        <>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-200/75">
            Választható következő lépés
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {lepesek.map((akcio) => (
              <button
                key={akcio}
                type="button"
                onClick={() => inditas(akcio)}
                disabled={Boolean(futo)}
                className="group rounded-2xl border border-white/10 bg-white/[0.025] p-4 text-left hover:-translate-y-0.5 hover:border-amber-300/35 hover:bg-amber-300/[0.05] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="text-sm font-semibold text-slate-100 group-hover:text-amber-100">
                  {AKCIO_FELIRATOK[akcio].cim}
                </span>
                <span className="mt-2 block text-xs leading-5 text-slate-500">
                  {futo === akcio
                    ? "Fut…"
                    : AKCIO_FELIRATOK[akcio].leiras}
                </span>
              </button>
            ))}
          </div>
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

      {eredmeny && (
        <div className="mt-5 rounded-2xl border border-white/8 bg-black/20 p-5">
          <Eredmeny action={eredmeny.action} adat={eredmeny.adat} />
        </div>
      )}
    </section>
  );
}
