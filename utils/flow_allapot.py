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
import uuid

from backend.career_state_machine import CareerIntent, CareerState, RULE_VERSION
from utils.adatbazis import kliens

SZABALYVERZIO = "flow-gps-v1"


def workflow_lekeres_vagy_letrehozas(
    user_id: str,
    session_id: str | None,
) -> dict | None:
    """A felhasználó egyetlen aktív, szerveroldali karrierfolyamata."""
    db = kliens()
    if not db:
        return None
    try:
        r = (db.schema("private").table("career_workflows")
               .select("id,current_state,intent,context,rule_version")
               .eq("user_id", user_id).eq("status", "active")
               .limit(1).execute())
        if r.data:
            return r.data[0]
        uj = db.schema("private").table("career_workflows").insert({
            "user_id": user_id,
            "session_id": session_id,
            "current_state": CareerState.CEL_TISZTAZATLAN.value,
            "context": {},
            "rule_version": RULE_VERSION,
            "status": "active",
        }).execute()
        return uj.data[0] if uj.data else None
    except Exception as exc:
        print(f"[flow_allapot] workflow hiba: {exc}")
        return None


def workflow_frissites(
    user_id: str,
    workflow_id: str,
    current_state: CareerState,
    intent: CareerIntent,
    context: dict | None = None,
) -> bool:
    """Csak a backend által már ellenőrzött állapotot menti el."""
    db = kliens()
    if not db:
        return False
    try:
        r = (db.schema("private").table("career_workflows").update({
                "current_state": current_state.value,
                "intent": intent.value,
                "context": context or {},
                "rule_version": RULE_VERSION,
                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            }).eq("id", workflow_id).eq("user_id", user_id).execute())
        return bool(r.data)
    except Exception as exc:
        print(f"[flow_allapot] workflow-frissites hiba: {exc}")
        return False


def workflow_ujrakezdes(user_id: str, workflow_id: str) -> bool:
    """A felhasználó kifejezett visszalépésére tiszta kezdőállapotot ment."""

    db = kliens()
    if not db:
        return False
    try:
        result = (
            db.schema("private")
            .table("career_workflows")
            .update({
                "current_state": CareerState.CEL_TISZTAZATLAN.value,
                "intent": None,
                "context": {},
                "rule_version": RULE_VERSION,
                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            })
            .eq("id", workflow_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data)
    except Exception as exc:
        print(f"[flow_allapot] workflow-ujrakezdes hiba: {exc}")
        return False


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


def vendeg_elozmeny_atadasa(
    user_id: str,
    session_id: str | None,
    atadas_azonosito: uuid.UUID | None,
    uzenetek: list[dict],
) -> str:
    """A böngészőben őrzött vendégbeszélgetést egyszer, tartósan átadja.

    A vendégüzenetek csak a sikeres belépés és az adatkezelési hozzájárulás
    után kerülnek a fiók szerveroldali előzményei közé. Minden sor azonosítója
    determinisztikusan az átadás UUID-jából és a sorszámból készül. Emiatt egy
    F5, hálózati újrapróbálás vagy két párhuzamos böngészőhívás sem tudja
    megduplázni a beszélgetést: ugyanazokra az elsődleges kulcsokra fut.

    A több sort egyetlen PostgREST-upsert küldi az adatbázisba, tehát nem
    maradhat félbehagyott, részben átköltöztetett beszélgetés.
    """

    if not uzenetek:
        return "nincs"
    db = kliens()
    if not db or not session_id or not atadas_azonosito:
        return "hiba"

    most = datetime.datetime.now(datetime.UTC)
    sorok = []
    for sorszam, uzenet in enumerate(uzenetek[:6]):
        szerep = uzenet.get("szerep")
        tartalom = str(uzenet.get("szoveg") or "").strip()
        if szerep not in {"user", "flow"} or not tartalom:
            continue
        uzenet_id = uuid.uuid5(atadas_azonosito, str(sorszam))
        sorok.append({
            "id": str(uzenet_id),
            "session_id": session_id,
            "user_id": user_id,
            "szerep": szerep,
            "tartalom": tartalom[:600],
            "strukturalt_hivatkozasok": [{
                "tipus": "vendeg_atadas",
                "azonosito": str(atadas_azonosito),
                "sorszam": sorszam,
            }],
            # A meglévő visszaolvasás idő szerint rendez. Mikromásodperces
            # eltérés őrzi a vendégbeszélgetés eredeti sorrendjét.
            "letrehozva": (
                most + datetime.timedelta(microseconds=sorszam)
            ).isoformat(),
        })

    if not sorok:
        return "nincs"

    try:
        tabla = db.schema("private").table("flow_messages")
        azonosito_lista = [sor["id"] for sor in sorok]
        korabbi = (
            tabla.select("id,user_id")
            .in_("id", azonosito_lista)
            .execute()
        )
        korabbi_talalatok = {
            sor["id"]: sor["user_id"] for sor in (korabbi.data or [])
        }
        if len(korabbi_talalatok) == len(sorok):
            return (
                "mar_atadva"
                if all(
                    korabbi_talalatok.get(sor["id"]) == user_id
                    for sor in sorok
                )
                else "hiba"
            )

        tabla.upsert(
            sorok,
            on_conflict="id",
            ignore_duplicates=True,
        ).execute()
        ellenorzes = (
            tabla.select("id,user_id")
            .in_("id", azonosito_lista)
            .execute()
        )
        talalatok = {
            sor["id"]: sor["user_id"] for sor in (ellenorzes.data or [])
        }
        return (
            "atadva"
            if all(
                talalatok.get(sor["id"]) == user_id
                for sor in sorok
            )
            else "hiba"
        )
    except Exception as exc:
        print(f"[flow_allapot] vendeg-atadas hiba: {exc}")
        return "hiba"


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
