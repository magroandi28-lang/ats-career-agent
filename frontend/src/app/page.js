"use client";

import { useState } from "react";
import KarrierUgynok from "./KarrierUgynok";
import AuthMenu from "./AuthMenu";
import { apiFetch } from "../lib/api";

// Flow üzeneteiben ezt a jelölést keressük: [FLOW_AKCIO:karrier_ugynok:SZAKMA]
// Ha megvan, Flow eldöntötte, hogy a felhasználó állást keres, és tudja is
// már a célszakmát -- ilyenkor a jelölést kivágjuk a megjelenő szövegből, és
// elindítjuk a Karrier Ügynök automatizált láncát azzal a szakmával.
const AKCIO_MINTA = /\[FLOW_AKCIO:karrier_ugynok:([^\]]+)\]/;

const GYORS_VALASZOK = [
  "Állást keresnék",
  "Csak tanácsot szeretnék",
  "Bizonytalan vagyok, min kellene váltanom",
];

export default function Home() {
  const [uzenetek, setUzenetek] = useState([
    {
      szerep: "flow",
      szoveg:
        "Szia! Flow vagyok — itt vagyok, hogy segítsek eligazodni, bármi is foglalkoztat az állásod/karriered kapcsán. Írd le nyugodtan a saját szavaiddal, mire van szükséged, vagy válassz az alábbiak közül.",
    },
  ]);
  const [szoveg, setSzoveg] = useState("");
  const [kuldesFolyamatban, setKuldesFolyamatban] = useState(false);
  const [hiba, setHiba] = useState(null);
  const [karrierSzakma, setKarrierSzakma] = useState(null);

  async function uzenetKuldese(uzenetSzoveg) {
    const tiszta = uzenetSzoveg.trim();
    if (!tiszta || kuldesFolyamatban) return;

    setHiba(null);
    const ujElozmenyek = [...uzenetek, { szerep: "user", szoveg: tiszta }];
    setUzenetek(ujElozmenyek);
    setSzoveg("");
    setKuldesFolyamatban(true);

    try {
      const valasz = await apiFetch("/flow-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kerdes: tiszta,
          profil: {},
          app_ismeret:
            "A Karrier-Ügynökség oldal segít állást keresni, CV-t átírni, " +
            "ATS-esélyt megnézni és motivációs levelet írni.",
          elozmenyek: ujElozmenyek,
        }),
      });
      if (!valasz.ok) throw new Error(`flow-chat: ${valasz.status}`);
      const adat = await valasz.json();
      let flowSzoveg = adat.valasz || "";

      const talalat = flowSzoveg.match(AKCIO_MINTA);
      let ujSzakma = null;
      if (talalat) {
        ujSzakma = talalat[1].trim();
        flowSzoveg = flowSzoveg.replace(AKCIO_MINTA, "").trim();
      }

      setUzenetek((elozo) => [...elozo, { szerep: "flow", szoveg: flowSzoveg }]);
      if (ujSzakma) setKarrierSzakma(ujSzakma);
    } catch (err) {
      setHiba(String(err));
    } finally {
      setKuldesFolyamatban(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 px-4 py-10 font-sans text-zinc-900">
      <div className="mx-auto max-w-2xl">
        <div className="mb-1 flex items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold">Karrier-Ügynökség</h1>
          <AuthMenu />
        </div>
        <p className="mb-6 text-sm text-zinc-500">
          Flow itt van, hogy meghallgasson és a megfelelő segítséghez vezessen.
        </p>

        <div className="mb-4 flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4">
          {uzenetek.map((u, i) => (
            <div
              key={i}
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                u.szerep === "flow"
                  ? "self-start bg-amber-50 text-zinc-800"
                  : "self-end bg-zinc-900 text-white"
              }`}
            >
              {u.szoveg}
            </div>
          ))}
          {kuldesFolyamatban && (
            <div className="self-start rounded-lg bg-amber-50 px-3 py-2 text-sm text-zinc-500">
              Flow gondolkodik…
            </div>
          )}
        </div>

        {!karrierSzakma && (
          <div className="mb-4 flex flex-wrap gap-2">
            {GYORS_VALASZOK.map((valasz) => (
              <button
                key={valasz}
                onClick={() => uzenetKuldese(valasz)}
                disabled={kuldesFolyamatban}
                className="rounded-full border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                {valasz}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            uzenetKuldese(szoveg);
          }}
          className="mb-8 flex gap-2"
        >
          <input
            value={szoveg}
            onChange={(e) => setSzoveg(e.target.value)}
            placeholder="Írd le szabadon, mire van szükséged…"
            className="flex-1 rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-500"
          />
          <button
            type="submit"
            disabled={kuldesFolyamatban}
            className="rounded-lg bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Küldés
          </button>
        </form>

        {hiba && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Hiba történt: {hiba}
          </div>
        )}

        {karrierSzakma && (
          <div className="border-t border-zinc-200 pt-6">
            <p className="mb-3 text-sm text-zinc-500">
              Flow elindította a Karrier Ügynök keresést:
            </p>
            <KarrierUgynok kezdoSzakma={karrierSzakma} />
          </div>
        )}
      </div>
    </div>
  );
}
