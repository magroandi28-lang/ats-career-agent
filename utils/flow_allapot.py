# -*- coding: utf-8 -*-
"""Flow és Career GPS állapot-rétege — a private.flow_sessions,
private.flow_messages, private.career_gps_events, private.career_gps_snapshots
táblákat kezeli (lásd supabase/migrations/20260724072136_flow_career_gps_foundation.sql).

FONTOS ELV (02-flow-career-gps.md, 4. pont): ez a réteg tisztán
determinisztikus -- Flow (az LLM) sosem ír ide közvetlenül, csak a backend,
és csak sikeres, ellenőrzött esemény nyomán. Az itt tárolt előzmény a
"forrás igazság", nem a kliens által küldött üzenetlista.

MEGJEGYZÉS: a supabase-py kliens alapból a "public" sémát nézi. Ezek a
táblák szándékosan a "private" sémában vannak (böngésző soha nem éri el),
ezért minden hívásnál kifejezetten jelezni kell: db.schema("private").table(...).
"""

import datetime

from utils.adatbazis import kliens

SZABALYVERZIO = "flow-gps-v1"


def session_lekeres_vagy_letrehozas(user_id: str) -> str | None:
    """Visszaadja a felhasználó aktív flow_sessions sorának id-ját, vagy
    létrehoz egyet, ha még nincs. None, ha az adatbázis nem elérhető."""
    db = kliens()
    if not db:
        return None
    try:
        r = (db.schema("private").table("flow_sessions").select("id")
               .eq("user_id", user_id).eq("allapot", "aktiv")
               .order("utolso_aktivitas", desc=True).limit(1).execute())
        if r.data:
            session_id = r.data[0]["id"]
            db.schema("private").table("flow_sessions").update(
                {"utolso_aktivitas": datetime.datetime.utcnow().isoformat()}
            ).eq("id", session_id).execute()
            return session_id
        uj = db.schema("private").table("flow_sessions").insert(
            {"user_id": user_id, "allapot": "aktiv"}
        ).execute()
        return uj.data[0]["id"] if uj.data else None
    except Exception as e:
        print(f"[flow_allapot] session hiba: {e}")
        return None


def elozmenyek_lekerese(user_id: str, session_id: str | None, limit: int = 12) -> list[dict]:
    """A backend SAJÁT, tárolt előzménye -- nem a kliens állítása szerint."""
    db = kliens()
    if not db or not session_id:
        return []
    try:
        r = (db.schema("private").table("flow_messages").select("szerep, tartalom")
               .eq("session_id", session_id)
               .order("letrehozva", desc=True).limit(limit).execute())
        sorok = list(reversed(r.data or []))
        return [{"szerep": s["szerep"], "szoveg": s["tartalom"]} for s in sorok]
    except Exception as e:
        print(f"[flow_allapot] elozmeny hiba: {e}")
        return []


def uzenet_mentese(user_id: str, session_id: str | None, szerep: str,
                    tartalom: str, hivatkozasok: list | None = None) -> None:
    db = kliens()
    if not db or not session_id:
        return
    try:
        db.schema("private").table("flow_messages").insert({
            "session_id": session_id,
            "user_id": user_id,
            "szerep": szerep,
            "tartalom": tartalom,
            "strukturalt_hivatkozasok": hivatkozasok or [],
        }).execute()
    except Exception as e:
        print(f"[flow_allapot] uzenet-mentes hiba: {e}")


def gps_esemeny_rogzitese(user_id: str, session_id: str | None,
                           esemeny_tipus: str, payload: dict,
                           actor: str = "system") -> str | None:
    """Append-only: csak beszúr, sosem módosít. Visszaadja az esemény id-ját,
    hogy a snapshot tudjon rá hivatkozni."""
    db = kliens()
    if not db:
        return None
    try:
        r = db.schema("private").table("career_gps_events").insert({
            "user_id": user_id,
            "session_id": session_id,
            "esemeny_tipus": esemeny_tipus,
            "payload": payload,
            "szabalyverzio": SZABALYVERZIO,
            "actor": actor,
        }).execute()
        return r.data[0]["id"] if r.data else None
    except Exception as e:
        print(f"[flow_allapot] gps-esemeny hiba: {e}")
        return None


def gps_snapshot_frissites(user_id: str, terulet: str, allapot: str,
                            esemeny_id: str | None) -> None:
    """Upsert: egy (user_id, terulet) párhoz mindig egy aktuális sor van."""
    db = kliens()
    if not db:
        return
    try:
        db.schema("private").table("career_gps_snapshots").upsert({
            "user_id": user_id,
            "terulet": terulet,
            "allapot": allapot,
            "utolso_esemeny_id": esemeny_id,
            "frissitve": datetime.datetime.utcnow().isoformat(),
        }, on_conflict="user_id,terulet").execute()
    except Exception as e:
        print(f"[flow_allapot] snapshot hiba: {e}")


def gps_projekcio(user_id: str) -> list[dict]:
    """A felhasználó teljes, aktuális Career GPS állapota -- ez megy ki a
    GET /api/v1/career-gps végponton (későbbi csomag), és ez táplálja majd a
    frontend jobb oldali GPS-panelét is."""
    db = kliens()
    if not db:
        return []
    try:
        r = (db.schema("private").table("career_gps_snapshots").select("terulet, allapot, frissitve")
               .eq("user_id", user_id).execute())
        return r.data or []
    except Exception as e:
        print(f"[flow_allapot] projekcio hiba: {e}")
        return []
