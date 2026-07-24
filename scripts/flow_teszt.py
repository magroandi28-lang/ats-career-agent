# -*- coding: utf-8 -*-
"""Egyszeri, kézi teszt-szkript a mai Flow/Career GPS munkához.

NEM a végleges rendszer része -- csak arra való, hogy bejelentkezés/token
nélkül, közvetlenül kipróbáljuk: tényleg ír-e adatot a Supabase-be a ma
megírt flow_dontes() + flow_allapot réteg.

Futtatás a projekt gyökeréből:
    python scripts/flow_teszt.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.flow_agy import flow_dontes
from utils.flow_allapot import (
    session_lekeres_vagy_letrehozas,
    elozmenyek_lekerese,
    uzenet_mentese,
    gps_esemeny_rogzitese,
    gps_snapshot_frissites,
    gps_projekcio,
)

# Ezt a UUID-t a Supabase Dashboard Authentication > Users listájából másoltuk.
TESZT_USER_ID = "211aac3f-6d1b-4b94-b626-cbbfc5c57958"
TESZT_KERDES = "Szia, állást keresek, szoftvertesztelő vagyok."


def fut():
    print("1. Session lekérése/létrehozása...")
    session_id = session_lekeres_vagy_letrehozas(TESZT_USER_ID)
    print(f"   session_id = {session_id}")
    if not session_id:
        print("   HIBA: nincs session_id -- ellenőrizd a .env SUPABASE_* értékeit.")
        return

    print("2. Korábbi előzmény lekérése...")
    elozmenyek = elozmenyek_lekerese(TESZT_USER_ID, session_id)
    print(f"   {len(elozmenyek)} korábbi üzenet")

    print("3. Felhasználói üzenet mentése...")
    uzenet_mentese(TESZT_USER_ID, session_id, "user", TESZT_KERDES)

    print("4. Flow döntés kérése (valódi Gemini-hívás)...")
    dontes = flow_dontes(TESZT_KERDES, {}, "Karrier-Ügynökség teszt.", elozmenyek)
    print("   intent:", dontes.intent)
    print("   response_message:", dontes.response_message)
    print("   proposed_action:", dontes.proposed_action)
    print("   szakma:", dontes.szakma)
    print("   confidence:", dontes.confidence)

    print("5. Flow válaszának mentése...")
    uzenet_mentese(TESZT_USER_ID, session_id, "flow", dontes.response_message)

    if dontes.proposed_action == "karrier_ugynok_inditasa" and dontes.szakma:
        print("6. Career GPS esemény rögzítése...")
        esemeny_id = gps_esemeny_rogzitese(
            TESZT_USER_ID, session_id, "career_goal_selected",
            {"szakma": dontes.szakma}, actor="flow",
        )
        gps_snapshot_frissites(TESZT_USER_ID, "karriercel", "kivalasztott", esemeny_id)
        print(f"   esemeny_id = {esemeny_id}")
    else:
        print("6. Nem volt proposed_action -- nincs GPS-esemény ebben a körben.")

    print("7. Aktuális Career GPS állapot lekérése...")
    print("  ", gps_projekcio(TESZT_USER_ID))

    print("\nKÉSZ. Nézd meg a Supabase Table Editorban a private sémában:")
    print("  flow_sessions, flow_messages, career_gps_events, career_gps_snapshots")
    print("  -- kell látnod bennük ehhez a teszthez tartozó új sorokat.")


if __name__ == "__main__":
    fut()
