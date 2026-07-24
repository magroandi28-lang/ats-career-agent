"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";

const FIELD_CONFIG = {
  target_role: {
    field: "target_role",
    label: "Milyen pozíció vagy szakma a célod?",
    placeholder: "például: automata tesztelő",
  },
  skills: {
    field: "skills",
    label: "Mely készségeidre építhetünk?",
    placeholder: "Python, Playwright, SQL",
    list: true,
  },
  search_location: {
    field: "location",
    label: "Hol keresel munkát?",
    placeholder: "Budapest, Magyarország vagy távoli",
  },
  experience_or_project: {
    field: "projects",
    label: "Írj egy releváns tapasztalatot vagy projektet",
    placeholder: "Karrier-Ügynökség – AI-orchestráció és tesztelés",
    list: true,
  },
  cv_document: {
    field: "cv_document_id",
    label: "Töltsd fel a jelenlegi CV-det",
    file: true,
  },
  job_ad: {
    field: "job_ad_id",
    label: "Add meg a konkrét hirdetés linkjét",
    placeholder: "https://…",
  },
  career_context: {
    field: "career_goal",
    label: "Miben szeretnél most dönteni?",
    placeholder: "például: merre érdemes továbblépnem",
  },
  current_role: {
    field: "current_role",
    label: "Mi a jelenlegi vagy legutóbbi munkaköröd?",
    placeholder: "jelenlegi vagy legutóbbi szerep",
  },
  career_goal: {
    field: "career_goal",
    label: "Mit szeretnél elérni a váltással?",
    placeholder: "következő reális karriercél",
  },
  project: {
    field: "projects",
    label: "Melyik projektedet mutassuk be?",
    placeholder: "projekt neve és rövid célja",
    list: true,
  },
};

export default function ProfileGate({ onStateChange, embedded = false }) {
  const [profile, setProfile] = useState(null);
  const [values, setValues] = useState({});
  const [cvFile, setCvFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function loadProfile() {
    const response = await apiFetch("/api/v1/profile");
    if (!response.ok) throw new Error(`profile: ${response.status}`);
    const data = await response.json();
    setProfile(data);
    return data;
  }

  useEffect(() => {
    loadProfile().catch(() =>
      setError("A profiladatok most nem tölthetők be."),
    );
  }, []);

  const missing = profile?.readiness?.missing_fields || [];
  const configs = useMemo(
    () => missing.map((code) => ({ code, ...(FIELD_CONFIG[code] || {
      field: code,
      label: code,
      placeholder: "",
    }) })),
    [missing],
  );

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const fields = {};
      for (const config of configs) {
        if (config.file) continue;
        const raw = (values[config.field] || "").trim();
        if (!raw) throw new Error(`Hiányzó mező: ${config.label}`);
        fields[config.field] = config.list
          ? raw.split(",").map((item) => item.trim()).filter(Boolean)
          : raw;
      }

      if (configs.some((config) => config.file)) {
        if (!cvFile) throw new Error("Válassz ki egy PDF-formátumú CV-t.");
        const formData = new FormData();
        formData.append("fajl", cvFile);
        const upload = await apiFetch("/cv-feltoltes", {
          method: "POST",
          body: formData,
        });
        if (!upload.ok) throw new Error("A CV feltöltése nem sikerült.");
        const uploadData = await upload.json();
        fields.cv_document_id = uploadData.utvonal;
      }

      const draft = await apiFetch("/api/v1/profile/draft", {
        method: "PATCH",
        body: JSON.stringify({ fields }),
      });
      if (!draft.ok) throw new Error("A profilvázlat mentése nem sikerült.");

      const confirm = await apiFetch("/api/v1/profile/confirm", {
        method: "POST",
        body: JSON.stringify({
          fields: Object.keys(fields),
          reason: "user_confirmation",
        }),
      });
      if (!confirm.ok) throw new Error("A profil megerősítése nem sikerült.");
      const result = await confirm.json();
      await loadProfile();
      setValues({});
      setCvFile(null);
      onStateChange?.(result);
    } catch (submitError) {
      setError(submitError.message || "A mentés nem sikerült.");
    } finally {
      setBusy(false);
    }
  }

  if (!profile) {
    return (
      <div className="mt-4 text-sm text-slate-400">
        A szükséges profiladatok betöltése…
      </div>
    );
  }

  if (profile.readiness?.ready) {
    return (
      <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-300/[0.06] p-4">
        <p className="text-sm font-semibold text-emerald-100">
          A választott feladathoz szükséges profiladatok rendben vannak.
        </p>
        <p className="mt-1 text-xs text-emerald-100/65">
          Flow most már csak a jóváhagyott célhoz tartozó modult indíthatja.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={submit}
      className={
        embedded
          ? "mt-6"
          : "mt-4 rounded-2xl border border-amber-300/18 bg-amber-300/[0.04] p-4 sm:p-5"
      }
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-200/75">
        Következő ellenőrzött lépés
      </p>
      <h3 className="mt-2 text-base font-semibold text-white">
        Csak a mostani célhoz szükséges adatokat kérjük
      </h3>
      <div className="mt-4 grid gap-4">
        {configs.map((config) => (
          <label key={config.code} className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-300">
              {config.label}
            </span>
            {config.file ? (
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => setCvFile(event.target.files?.[0] || null)}
                className="block w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2.5 text-xs text-slate-300"
              />
            ) : (
              <input
                value={values[config.field] || ""}
                onChange={(event) =>
                  setValues((previous) => ({
                    ...previous,
                    [config.field]: event.target.value,
                  }))
                }
                placeholder={config.placeholder}
                className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:border-amber-300/45"
              />
            )}
          </label>
        ))}
      </div>
      {error && <p className="mt-3 text-xs text-red-200">{error}</p>}
      <button
        type="submit"
        disabled={busy}
        className="mt-4 rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:opacity-50"
      >
        {busy ? "Ellenőrzés és mentés…" : "Adatok jóváhagyása"}
      </button>
      <p className="mt-3 text-[11px] leading-5 text-slate-500">
        Ezek az adatok csak a jóváhagyás után válnak használható profilténnyé.
      </p>
    </form>
  );
}

