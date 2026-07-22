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

try:
    from jooble_gyujto import (  # noqa: E402
        keszsegek_kinyerese,
        gemini_kvota_elfogyott,
    )
    UJ_GEMINI_API = True
except ImportError:
    from jooble_gyujto import keszsegek_kinyerese  # noqa: E402

    UJ_GEMINI_API = False

    def gemini_kvota_elfogyott() -> bool:
        return False


# Napi legfeljebb 5 Gemini-hívás, hívásonként 10 hirdetéssel.
# Így Flow és a felhasználói funkciók számára is marad kvóta.
CSOMAG_MERET = max(1, int(os.getenv("KESZSEG_POTLO_CSOMAG_MERET", "10")))
MAX_CSOMAG = max(1, int(os.getenv("KESZSEG_POTLO_MAX_CSOMAG", "5")))


def hianyos_hirdetesek(db) -> list:
    """Hirdetések, amelyekhez egyetlen készség sincs kapcsolva."""
    mind, start = [], 0
    while True:
        r = (
            db.table("hirdetesek")
            .select("id, cim, snippet")
            .order("id")
            .range(start, start + 999)
            .execute()
        )
        adag = r.data or []
        mind.extend(adag)
        if len(adag) < 1000:
            break
        start += 1000

    van, start = set(), 0
    while True:
        r = (
            db.table("hirdetes_keszseg")
            .select("hirdetes_id")
            .range(start, start + 999)
            .execute()
        )
        adag = r.data or []
        van.update(s["hirdetes_id"] for s in adag)
        if len(adag) < 1000:
            break
        start += 1000

    return [
        h
        for h in mind
        if h["id"] not in van and (h.get("snippet") or "").strip()
    ]


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    varakozok = hianyos_hirdetesek(db)
    print(f"Készség nélküli hirdetések: {len(varakozok)}")

    if not varakozok:
        print("Nincs teendő — minden hirdetéshez van készség.")
        return

    feldolgozando = varakozok[: MAX_CSOMAG * CSOMAG_MERET]

    print(
        f"Mai keret: legfeljebb {MAX_CSOMAG} Gemini-hívás, "
        f"{len(feldolgozando)} hirdetés."
    )

    ures_egymas_utan = 0
    feldolgozva = 0

    for i in range(0, len(feldolgozando), CSOMAG_MERET):
        koteg = feldolgozando[i : i + CSOMAG_MERET]

        if UJ_GEMINI_API:
            keszsegek = keszsegek_kinyerese(koteg, kenyszerit=True)
        else:
            keszsegek = keszsegek_kinyerese(koteg)

        if gemini_kvota_elfogyott():
            print(
                "\nA Gemini-keret elfogyott — "
                "a következő futás innen folytatja."
            )
            break

        if all(not k for k in keszsegek):
            ures_egymas_utan += 1
            if ures_egymas_utan >= 2:
                print(
                    "\nA Gemini-keret valószínűleg elfogyott — "
                    "a következő futás innen folytatja."
                )
                break
            continue

        ures_egymas_utan = 0

        for hird, klista in zip(koteg, keszsegek):
            if klista:
                try:
                    _keszsegek_ment(db, hird["id"], klista)
                    feldolgozva += 1
                except Exception as e:
                    print(f"Mentési hiba ({hird['id']}): {e}")

        print(f"Pótolva: {feldolgozva} hirdetés")
        time.sleep(1)

    if feldolgozva:
        print("Készségnév-normalizálás...")
        keszsegnev_normalizalas()

    print(f"\nKÉSZ: {feldolgozva} hirdetéshez pótoltunk készségeket.")

    hatralevo = max(0, len(varakozok) - feldolgozva)
    print(
        f"Még hátralévő címkétlen hirdetés: körülbelül {hatralevo}. "
        "A következő napi futás automatikusan folytatja."
    )


if __name__ == "__main__":
    main()
