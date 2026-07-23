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
          className="flex-1 rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: "#141d33", border: "1px solid #2a3550", color: "#e6ebf7" }}
        />
        <input
          value={helyszin}
          onChange={(e) => setHelyszin(e.target.value)}
          placeholder="Város"
          className="w-full rounded-lg px-3 py-2 text-sm outline-none sm:w-32"
          style={{ background: "#141d33", border: "1px solid #2a3550", color: "#e6ebf7" }}
        />
        <button
          type="submit"
          disabled={dolgozik}
          className="rounded-lg px-5 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: "#e0b84a", color: "#1a1305" }}
        >
          {dolgozik
            ? futAllapot === "szakma"
              ? "Szakma felismerése…"
              : "Állások keresése…"
            : "Keresés"}
        </button>
      </form>

      {hiba && (
        <div
          className="mb-6 rounded-lg px-4 py-3 text-sm"
          style={{ background: "#3a1a1a", border: "1px solid #5a2a2a", color: "#f0a0a0" }}
        >
          Hiba történt: {hiba}
        </div>
      )}

      {szakmaInfo && (
        <div
          className="mb-6 rounded-lg p-4"
          style={{ background: "#141d33", border: "1px solid #232e4d" }}
        >
          <p className="text-sm" style={{ color: "#7a88ad" }}>Felismert szakma</p>
          <p className="mb-2 text-lg font-medium" style={{ color: "#f0d896" }}>
            {szakmaInfo.szakma}
          </p>
          {szakmaInfo.utos_kulcsszavak?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {szakmaInfo.utos_kulcsszavak.map((k) => (
                <span
                  key={k}
                  className="rounded-full px-2.5 py-0.5 text-xs"
                  style={{ background: "#1c2544", color: "#cdd6ee" }}
                >
                  {k}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {eredmeny && !eredmeny.van_jo_talalat && (
        <div
          className="mb-4 rounded-lg px-4 py-3 text-sm"
          style={{ background: "#3a2f14", border: "1px solid #5a4a1f", color: "#e0c896" }}
        >
          Ebben a szakmában most nincs 80%+ egyezésű friss hirdetés
          ({helyszin}). Az alábbiak a legjobb elérhető találatok.
        </div>
      )}

      {talalatok.length > 0 && (
        <ul className="flex flex-col gap-3">
          {talalatok.map((allas, i) => (
            <li
              key={allas.id ?? i}
              className="rounded-lg p-4"
              style={{ background: "#141d33", border: "1px solid #232e4d" }}
            >
              <div className="mb-1 flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium" style={{ color: "#f0d896" }}>{allas.cim}</p>
                  <p className="text-sm" style={{ color: "#7a88ad" }}>
                    {allas.ceg}
                    {allas.helyszin ? ` · ${allas.helyszin}` : ""}
                  </p>
                </div>
                <span
                  className="shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold"
                  style={{ background: "#173328", color: "#4ade80" }}
                >
                  {allas.illeszkedes ?? 0}% egyezés
                </span>
              </div>
              {allas.snippet && (
                <p className="mb-2 text-sm" style={{ color: "#cdd6ee" }}>{allas.snippet}</p>
              )}
              {allas.bersav && (
                <p className="mb-2 text-xs" style={{ color: "#7a88ad" }}>💰 {allas.bersav}</p>
              )}
              {allas.link && (
                <a
                  href={allas.link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium underline"
                  style={{ color: "#e0b84a" }}
                >
                  Megnézem a hirdetést →
                </a>
              )}
            </li>
          ))}
        </ul>
      )}

      {eredmeny && talalatok.length === 0 && (
        <p className="text-sm" style={{ color: "#7a88ad" }}>
          Nincs megjeleníthető találat ehhez a szakmához/városhoz.
        </p>
      )}
    </div>
  );
}
