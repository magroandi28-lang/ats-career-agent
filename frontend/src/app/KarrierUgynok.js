"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

// Ez a komponens a Karrier Ügynök automatizált láncát adja: szakma
// felismerése -> állások keresése. Flow (page.js) hívja meg, amikor
// felismeri, hogy a felhasználó állást keres -- ilyenkor a "kezdoSzakma"
// propon keresztül azonnal el is indítja a keresést, kattintás nélkül.
// Kézi használatra (Flow nélkül, közvetlen teszteléshez) is megáll a lábán:
// kezdoSzakma nélkül egy sima keresőmezőt mutat.
export default function KarrierUgynok({ kezdoSzakma = "", kezdoHelyszin = "Budapest" }) {
  const [szakmaMegadva, setSzakmaMegadva] = useState(kezdoSzakma);
  const [helyszin, setHelyszin] = useState(kezdoHelyszin);
  const [futAllapot, setFutAllapot] = useState("keszen"); // keszen | szakma | allasok
  const [hiba, setHiba] = useState(null);
  const [szakmaInfo, setSzakmaInfo] = useState(null);
  const [eredmeny, setEredmeny] = useState(null);

  async function kereses(szakmaSzoveg, helyszinSzoveg) {
    if (!szakmaSzoveg.trim()) return;

    setHiba(null);
    setSzakmaInfo(null);
    setEredmeny(null);

    try {
      setFutAllapot("szakma");
      const szResp = await apiFetch("/szakma-felismeres", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ szakma_megadva: szakmaSzoveg }),
      });
      if (!szResp.ok) throw new Error(`szakma-felismeres: ${szResp.status}`);
      const szInfo = await szResp.json();
      setSzakmaInfo(szInfo);

      setFutAllapot("allasok");
      const alResp = await apiFetch("/allasok", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ szakma_info: szInfo, helyszin: helyszinSzoveg }),
      });
      if (!alResp.ok) throw new Error(`allasok: ${alResp.status}`);
      const alEredmeny = await alResp.json();
      setEredmeny(alEredmeny);
    } catch (err) {
      setHiba(String(err));
    } finally {
      setFutAllapot("keszen");
    }
  }

  // Ha Flow már tudja a célszakmát, azonnal, kattintás nélkül elindul a keresés.
  useEffect(() => {
    if (kezdoSzakma) {
      kereses(kezdoSzakma, kezdoHelyszin);
    }
    // csak az induláskor, ha van eloretoltott szakma
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const talalatok = eredmeny?.top_5 || eredmeny?.legjobb_elerheto || [];
  const dolgozik = futAllapot !== "keszen";

  return (
    <div className="w-full">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          kereses(szakmaMegadva, helyszin);
        }}
        className="mb-6 flex flex-col gap-3 sm:flex-row"
      >
        <input
          value={szakmaMegadva}
          onChange={(e) => setSzakmaMegadva(e.target.value)}
          placeholder="Milyen szakma? Pl. bolti eladó, szoftverfejlesztő..."
          className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500"
        />
        <input
          value={helyszin}
          onChange={(e) => setHelyszin(e.target.value)}
          placeholder="Város"
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500 sm:w-32"
        />
        <button
          type="submit"
          disabled={dolgozik}
          className="rounded-lg bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {dolgozik
            ? futAllapot === "szakma"
              ? "Szakma felismerése…"
              : "Állások keresése…"
            : "Keresés"}
        </button>
      </form>

      {hiba && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Hiba történt: {hiba}
        </div>
      )}

      {szakmaInfo && (
        <div className="mb-6 rounded-lg border border-zinc-200 bg-white p-4">
          <p className="text-sm text-zinc-500">Felismert szakma</p>
          <p className="mb-2 text-lg font-medium">{szakmaInfo.szakma}</p>
          {szakmaInfo.utos_kulcsszavak?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {szakmaInfo.utos_kulcsszavak.map((k) => (
                <span
                  key={k}
                  className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs text-zinc-600"
                >
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {eredmeny && !eredmeny.van_jo_talalat && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Ebben a szakmában most nincs 80%+ egyezésű friss hirdetés
          ({helyszin}). Az alábbiak a legjobb elérhető találatok.
        </div>
      )}

      {talalatok.length > 0 && (
        <ul className="flex flex-col gap-3">
          {talalatok.map((allas, i) => (
            <li
              key={allas.id ?? i}
              className="rounded-lg border border-zinc-200 bg-white p-4"
            >
              <div className="mb-1 flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{allas.cim}</p>
                  <p className="text-sm text-zinc-500">
                    {allas.ceg}
                    {allas.helyszin ? ` · ${allas.helyszin}` : ""}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  {allas.illeszkedes ?? 0}% egyezés
                </span>
              </div>
              {allas.snippet && (
                <p className="mb-2 text-sm text-zinc-600">{allas.snippet}</p>
              )}
              {allas.bersav && (
                <p className="mb-2 text-xs text-zinc-500">💰 {allas.bersav}</p>
              )}
              {allas.link && (
                <a
                  href={allas.link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-zinc-900 underline"
                >
                  Megnézem a hirdetést →
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      {eredmeny && talalatok.length === 0 && (
        <p className="text-sm text-zinc-500">
          Nincs megjeleníthető találat ehhez a szakmához/városhoz.
        </p>
      )}
    </div>
  );
}
