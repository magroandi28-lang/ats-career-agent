# -*- coding: utf-8 -*-
"""KÉSZSÉG-PÓTLÓ — a készség nélkül mentett hirdetések utólagos feldolgozása.

Ha a gyűjtéskor elfogyott a Gemini-keret, a hirdetések készség nélkül
kerültek be. Ez a script megkeresi őket, és pótolja a készség-kinyerést.
ÚJRAFUTTATHATÓ: mindig csak a hiányosakat dolgozza fel; ha a kvóta újra
elfogy, magától leáll, és legközelebb onnan folytatja.

Futtatás:  python scripts/keszseg_potlo.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.adatbazis import kliens, keszsegnev_normalizalas, _keszsegek_ment  # noqa: E402
from jooble_gyujto import keszsegek_kinyerese, CSOMAG_MERET  # noqa: E402


def hianyos_hirdetesek(db) -> list:
    """Hirdetések, amelyekhez EGYETLEN készség sincs kapcsolva."""
    # Az összes hirdetés (lapozva)
    mind, start = [], 0
    while True:
        r = (db.table("hirdetesek").select("id, cim, snippet")
               .order("id").range(start, start + 999).execute())
        adag = r.data or []
        mind.extend(adag)
        if len(adag) < 1000:
            break
        start += 1000

    # Amelyekhez van készség (lapozva)
    van, start = set(), 0
    while True:
        r = (db.table("hirdetes_keszseg").select("hirdetes_id")
               .range(start, start + 999).execute())
        adag = r.data or []
        van.update(s["hirdetes_id"] for s in adag)
        if len(adag) < 1000:
            break
        start += 1000

    return [h for h in mind if h["id"] not in van and (h.get("snippet") or "").strip()]


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    varakozok = hianyos_hirdetesek(db)
    print(f"Keszseg nelkuli hirdetesek: {len(varakozok)}")
    if not varakozok:
        print("Nincs teendo — minden hirdeteshez van keszseg.")
        return

    ures_egymas_utan = 0
    feldolgozva = 0
    for i in range(0, len(varakozok), CSOMAG_MERET):
        koteg = varakozok[i:i + CSOMAG_MERET]
        keszsegek = keszsegek_kinyerese(koteg)

        if all(not k for k in keszsegek):
            ures_egymas_utan += 1
            if ures_egymas_utan >= 2:
                print("\nA Gemini-keret valoszinuleg elfogyott — "
                      "futtasd ujra kesobb, onnan folytatja.")
                break
            continue
        ures_egymas_utan = 0

        for hird, klista in zip(koteg, keszsegek):
            if klista:
                try:
                    _keszsegek_ment(db, hird["id"], klista)
                    feldolgozva += 1
                except Exception as e:
                    print(f"  Mentes hiba ({hird['id']}): {e}")
        print(f"  Potolva: {feldolgozva} hirdetes")
        time.sleep(1)

    if feldolgozva:
        print("Keszsegnev-normalizalas...")
        keszsegnev_normalizalas()
    print(f"\nKESZ: {feldolgozva} hirdeteshez potoltunk keszsegeket.")


if __name__ == "__main__":
    main()
