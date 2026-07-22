"use client";

import { useEffect, useState } from "react";

// A backend cime -- kornyezeti valtozobol jon, hogy kesobb (Vercel-en
// elesben) mas cimre lehessen allitani atirogatas nelkul.
const API_CIM = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [allapot, setAllapot] = useState("betöltés...");
  const [hiba, setHiba] = useState(null);

  useEffect(() => {
    fetch(`${API_CIM}/healthz`)
      .then((valasz) => valasz.json())
      .then((adat) => setAllapot(adat.uzenet))
      .catch((e) => setHiba(String(e)));
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 font-sans">
      <h1 className="text-2xl font-semibold">Karrier-Ügynökség</h1>
      <p className="text-lg">
        Backend állapota:{" "}
        <span className="font-bold">
          {hiba ? `HIBA: ${hiba}` : allapot}
        </span>
      </p>
    </div>
  );
}
