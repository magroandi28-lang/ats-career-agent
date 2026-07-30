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

async function responseError(response, fallback) {
  try {
    const body = await response.json();
    return body.detail || fallback;
  } catch {
    return fallback;
  }
}

export default function ProfileGate({
  onStateChange,
  embedded = false,
  forceCvUpload = false,
}) {
  const [profile, setProfile] = useState(null);
  const [values, setValues] = useState({});
  const [cvFile, setCvFile] = useState(null);
  const [cvImport, setCvImport] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // A CV-ből felismert célmunkakör-javaslatok. A jóváhagyás válaszából
  // jönnek, és csak felkínáljuk őket -- a döntés a felhasználóé.
  const [szakmaJavaslatok, setSzakmaJavaslatok] = useState([]);

  async function loadProfile() {
    const response = await apiFetch("/api/v1/profile");
    if (!response.ok) throw new Error(`profile: ${response.status}`);
    const data = await response.json();
    setProfile(data);
    setValues((previous) => {
      const next = { ...previous };
      for (const [field, value] of Object.entries(data.draft_data || {})) {
        if (next[field] !== undefined) continue;
        next[field] = Array.isArray(value) ? value.join(", ") : value;
      }
      return next;
    });
    return data;
  }

  async function restorePendingImport(profileData) {
    if (!profileData?.readiness?.missing_fields?.includes("cv_document")) {
      window.localStorage.removeItem("career_pending_cv_import");
      return;
    }
    const importId = window.localStorage.getItem("career_pending_cv_import");
    if (!importId) return;
    const response = await apiFetch(`/api/v1/profile/imports/${importId}`);
    if (!response.ok) {
      window.localStorage.removeItem("career_pending_cv_import");
      return;
    }
    const data = await response.json();
    if (data.review_status !== "pending") {
      window.localStorage.removeItem("career_pending_cv_import");
      return;
    }
    setCvImport(data);
    setExtractedText(data.extracted_text || "");
  }

  useEffect(() => {
    loadProfile()
      .then(restorePendingImport)
      .catch(() => setError("A profiladatok most nem tölthetők be."));
  }, []);

  // A legelső „Van CV-m" válasz még nem karriercél. Ilyenkor semleges
  // CV-importot mutatunk, és csak a jóváhagyott CV után kérdezzük meg,
  // merre készül. Nem választunk helyette idő előtt CV-szolgáltatást.
  const missing = forceCvUpload
    ? profile?.confirmed_data?.cv_document_id
      ? []
      : ["cv_document"]
    : profile?.readiness?.missing_fields || [];
  const configs = useMemo(
    () =>
      missing.map((code) => ({
        code,
        ...(FIELD_CONFIG[code] || {
          field: code,
          label: code,
          placeholder: "",
        }),
      })),
    [missing],
  );
  const fieldConfigs = configs.filter((config) => !config.file);
  const needsCv = configs.some((config) => config.file);

  async function confirmFields(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const fields = {};
      for (const config of fieldConfigs) {
        const raw = (values[config.field] || "").trim();
        if (!raw) throw new Error(`Hiányzó mező: ${config.label}`);
        fields[config.field] = config.list
          ? raw
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : raw;
      }

      const draft = await apiFetch("/api/v1/profile/draft", {
        method: "PATCH",
        body: JSON.stringify({ fields }),
      });
      if (!draft.ok) {
        throw new Error(
          await responseError(draft, "A profilvázlat mentése nem sikerült."),
        );
      }

      const confirm = await apiFetch("/api/v1/profile/confirm", {
        method: "POST",
        body: JSON.stringify({
          fields: Object.keys(fields),
          reason: "user_confirmation",
        }),
      });
      if (!confirm.ok) {
        throw new Error(
          await responseError(confirm, "A profil megerősítése nem sikerült."),
        );
      }
      const result = await confirm.json();
      await loadProfile();
      onStateChange?.(result);
    } catch (submitError) {
      setError(submitError.message || "A mentés nem sikerült.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadCv(event) {
    event.preventDefault();
    if (!cvFile) {
      setError("Válassz ki egy PDF-formátumú CV-t.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("fajl", cvFile);
      const response = await apiFetch("/api/v1/profile/import", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(
          await responseError(response, "A CV feltöltése nem sikerült."),
        );
      }
      const result = await response.json();
      window.localStorage.setItem("career_pending_cv_import", result.id);
      setCvImport(result);
      setExtractedText(result.extracted_text || "");
      setCvFile(null);
    } catch (uploadError) {
      setError(uploadError.message || "A CV feltöltése nem sikerült.");
    } finally {
      setBusy(false);
    }
  }

  async function approveCv() {
    setBusy(true);
    setError(null);
    try {
      const response = await apiFetch("/api/v1/profile/facts/review", {
        method: "POST",
        body: JSON.stringify({
          import_id: cvImport.id,
          approved_text: extractedText,
        }),
      });
      if (!response.ok) {
        throw new Error(
          await responseError(response, "A CV jóváhagyása nem sikerült."),
        );
      }
      const result = await response.json();
      // A CV-ből felismert szakmák: a célmunkakör mező fölött jelennek meg,
      // egy kattintással választhatóan.
      setSzakmaJavaslatok(result.celmunkakor_javaslatok || []);
      window.localStorage.removeItem("career_pending_cv_import");
      setCvImport(null);
      setExtractedText("");
      await loadProfile();
      onStateChange?.(result);
    } catch (approvalError) {
      setError(approvalError.message || "A CV jóváhagyása nem sikerült.");
    } finally {
      setBusy(false);
    }
  }

  function chooseAnotherCv() {
    window.localStorage.removeItem("career_pending_cv_import");
    setCvImport(null);
    setExtractedText("");
    setCvFile(null);
    setError(null);
  }

  if (!profile) {
    return (
      <div className="mt-4 text-sm text-slate-400">
        A szükséges profiladatok betöltése…
      </div>
    );
  }

  if (!forceCvUpload && profile.readiness?.ready) {
    return (
      <div className="mt-6 rounded-2xl border border-emerald-300/20 bg-emerald-300/[0.06] p-5">
        <p className="text-sm font-semibold text-emerald-100">
          A CV és a választott célhoz szükséges adatok jóvá vannak hagyva.
        </p>
        <p className="mt-2 text-xs leading-5 text-emerald-100/65">
          A feltöltés önmagában nem aktiválta a dokumentumot: csak az átnézett
          szöveg külön jóváhagyása után került a profilodba.
        </p>
      </div>
    );
  }

  const shellClass = embedded
    ? "mt-6"
    : "mt-4 rounded-2xl border border-amber-300/18 bg-amber-300/[0.04] p-4 sm:p-5";

  if (fieldConfigs.length > 0) {
    return (
      <form onSubmit={confirmFields} className={shellClass}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-200/75">
          Következő ellenőrzött lépés
        </p>
        <h3 className="mt-2 text-base font-semibold text-white">
          Előbb a választott célhoz hiányzó adatokat pontosítsuk
        </h3>
        <div className="mt-4 grid gap-4">
          {fieldConfigs.map((config) => (
            <label key={config.code} className="block">
              <span className="mb-1.5 block text-xs font-medium text-slate-300">
                {config.label}
              </span>

              {/* A CV-BŐL FELISMERT SZAKMÁK, EGY KATTINTÁSSAL.
                  Ami a CV-ben ott van, azt ne kelljen begépelni. A javaslat
                  mellett látszik, MELYIK sor hozta -- így eldönthető, jó-e.
                  Nem választunk automatikusan: egy emberben több szakmai
                  profil is lehet (pénztáros és bolti eladó egyszerre), és a
                  célmunkakör nem azonos a jelenlegivel. */}
              {config.field === "target_role" &&
                szakmaJavaslatok.length > 0 && (
                  <div className="mb-2">
                    <p className="mb-1.5 text-[11px] text-slate-500">
                      A CV-d alapján ezeket ismertük fel — válassz, vagy írj
                      be mást:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {szakmaJavaslatok.map((javaslat) => {
                        const kivalasztott =
                          values.target_role === javaslat.szakma;
                        return (
                          <button
                            key={javaslat.szakma}
                            type="button"
                            title={`A CV-ben: „${javaslat.bizonyitek}”`}
                            onClick={() =>
                              setValues((previous) => ({
                                ...previous,
                                target_role: javaslat.szakma,
                              }))
                            }
                            className={`rounded-full border px-3 py-1 text-xs ${
                              kivalasztott
                                ? "border-amber-300 bg-amber-300 font-semibold text-slate-950"
                                : "border-white/15 bg-white/[0.04] text-slate-200 hover:border-amber-300/50"
                            }`}
                          >
                            {javaslat.szakma}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

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
            </label>
          ))}
        </div>
        {error && <p className="mt-3 text-xs text-red-200">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="mt-4 rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:opacity-50"
        >
          {busy ? "Mentés…" : "Adatok jóváhagyása és folytatás"}
        </button>
        {needsCv && (
          <p className="mt-3 text-[11px] leading-5 text-slate-500">
            A CV feltöltése a következő külön lépés lesz.
          </p>
        )}
      </form>
    );
  }

  if (needsCv && !cvImport) {
    return (
      <form onSubmit={uploadCv} className={shellClass}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-200/75">
          CV feltöltése
        </p>
        <h3 className="mt-2 text-base font-semibold text-white">
          Válaszd ki a jelenlegi CV-d PDF-változatát
        </h3>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          A feltöltés után megmutatjuk a kinyert szöveget. Ekkor még semmit
          nem hagyunk jóvá és nem indítunk el automatikusan.
        </p>
        <input
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setCvFile(event.target.files?.[0] || null)}
          className="mt-4 block w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2.5 text-xs text-slate-300"
        />
        {error && <p className="mt-3 text-xs text-red-200">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="mt-4 rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:opacity-50"
        >
          {busy ? "Feltöltés és szövegkinyerés…" : "Feltöltés ellenőrzésre"}
        </button>
      </form>
    );
  }

  if (needsCv && cvImport) {
    return (
      <section className={shellClass}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-200/75">
          Kinyert CV-szöveg ellenőrzése
        </p>
        <h3 className="mt-2 text-base font-semibold text-white">
          Nézd át, és javítsd, ha a PDF-ből valami pontatlanul olvasható
        </h3>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          Fájl: {cvImport.file_name} · {extractedText.length.toLocaleString("hu-HU")} karakter
        </p>
        <label className="mt-4 block">
          <span className="sr-only">Kinyert CV-szöveg</span>
          <textarea
            value={extractedText}
            onChange={(event) => setExtractedText(event.target.value)}
            rows={16}
            maxLength={120000}
            className="min-h-80 w-full resize-y rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 font-mono text-xs leading-5 text-slate-200 focus:border-amber-300/45"
          />
        </label>
        {error && <p className="mt-3 text-xs text-red-200">{error}</p>}
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={approveCv}
            disabled={busy || !extractedText.trim()}
            className="rounded-xl bg-amber-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-amber-200 disabled:opacity-50"
          >
            {busy ? "Jóváhagyás…" : "Átnéztem, jóváhagyom"}
          </button>
          <button
            type="button"
            onClick={chooseAnotherCv}
            disabled={busy}
            className="rounded-xl border border-white/12 px-5 py-3 text-sm font-semibold text-slate-300 hover:border-amber-300/35 hover:text-amber-100 disabled:opacity-50"
          >
            Másik PDF választása
          </button>
        </div>
        <p className="mt-3 text-[11px] leading-5 text-slate-500">
          Csak a külön jóváhagyás után válik ez a CV használható profilténnyé.
        </p>
      </section>
    );
  }

  if (forceCvUpload && profile.confirmed_data?.cv_document_id) {
    return (
      <div className={shellClass}>
        <p className="text-sm text-emerald-100">
          A jóváhagyott CV-d készen áll a következő kérdéshez.
        </p>
      </div>
    );
  }

  return (
    <div className={shellClass}>
      <p className="text-sm text-slate-400">
        Ehhez a célhoz most nincs további bekérendő adat.
      </p>
    </div>
  );
}
