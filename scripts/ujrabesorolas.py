# -*- coding: utf-8 -*-
"""A meglévő hirdetések újrabesorolása a MAI besorolóval.

MIÉRT KELL: a 96 kulcsszavas korszakban a szakma a KERESÉS paramétere volt,
nem a hirdetés tulajdonsága. Egy „AI mérnök" keresésre előjött konyhai
kisegítő hirdetés AI mérnök címkét kapott. Mérve 2026-07-29-én: 48 szakmánál
a hirdetéscímek kevesebb mint fele vezet ugyanoda, a „vezetőasszisztens"
187 hirdetéséből EGY sem.

A mai besoroló a CÍMBŐL dolgozik, tehát minden új besorolás igazolható a
hirdetés saját szövegével -- a régi csak egy keresőszóval volt az.

AMIT VÁLLALUNK: lesznek hirdetések, amikről a besoroló nem tud szakmát
mondani („Senior PHP Developer", „Áruházi munkatárs"). Azok szakma nélkül
maradnak. Kevesebb adat, de igaz -- a mostani állapot több adat, de hamis.
Rosszul besorolni rosszabb, mint nem besorolni: a piaci körkép egy téves
szakmában magabiztosan hibás bért mutat.

IDEMPOTENS: ugyanazon az adaton újrafuttatva semmit nem változtat, tehát
biztonságosan beköthető a napi futásba.

Futtatás:
    python scripts/ujrabesorolas.py          # próba, nem ír
    python scripts/ujrabesorolas.py --ir     # ment is
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.szakma_besorolo import Besorolo  # noqa: E402
from utils.adatbazis import kliens, szakma_ment  # noqa: E402

ADAG = 200


def _mind(db, tabla: str, mezok: str) -> list[dict]:
    sorok, kezdet = [], 0
    while True:
        adag = (db.table(tabla).select(mezok)
                  .range(kezdet, kezdet + 999).execute().data or [])
        sorok += adag
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


def main() -> int:
    ir = "--ir" in sys.argv
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase-kapcsolat.")
        return 1

    print(f"Újrabesorolás | mentés: {'IGEN' if ir else 'NEM (próba)'}")

    foglalkozasok = _mind(
        db, "esco_foglalkozas",
        "uri, nev, isco_kod, alt_nevek, nev_en, alt_nevek_en")
    for f in foglalkozasok:
        f["alt_nevek"] = (list(f.get("alt_nevek") or [])
                          + list(f.get("alt_nevek_en") or []))
    szakmak = _mind(db, "szakmak", "id, nev")
    besorolo = Besorolo(
        foglalkozasok, szakmak,
        _mind(db, "szakma_esco", "szakma_id, foglalkozas_uri"))
    nev_szerint = {s["id"]: s["nev"] for s in szakmak}

    hirdetesek = _mind(db, "hirdetesek", "id, cim, szakma_id")
    print(f"Hirdetés: {len(hirdetesek)}")

    # A besoroló találhat olyan ESCO-foglalkozást, amihez még nincs szakmánk.
    # Ilyenkor a szakma megszületik -- ugyanúgy, ahogy a söprésben.
    uj_szakma_cache: dict[str, int | None] = {}
    valtozasok: list[tuple[int, int | None]] = []
    mozgas: Counter = Counter()
    valtozatlan = 0

    for h in hirdetesek:
        regi = h.get("szakma_id")
        t = besorolo.besorol(h.get("cim") or "")

        if t is None:
            uj = None
        elif t.szakma_id is not None:
            uj = t.szakma_id
        else:
            # Új szakma kell hozzá.
            if t.szakma_nev not in uj_szakma_cache:
                uj_szakma_cache[t.szakma_nev] = (
                    szakma_ment({"szakma": t.szakma_nev,
                                 "szakma_kategoria": t.kategoria})
                    if ir else None
                )
            uj = uj_szakma_cache[t.szakma_nev]
            if not ir:
                mozgas[(nev_szerint.get(regi, "(nincs)"),
                        f"ÚJ: {t.szakma_nev}")] += 1
                continue

        if uj == regi:
            valtozatlan += 1
            continue
        valtozasok.append((h["id"], uj))
        mozgas[(nev_szerint.get(regi, "(nincs)"),
                nev_szerint.get(uj, "— nem besorolható —"))] += 1

    print(f"  Változatlan:   {valtozatlan}")
    print(f"  Módosulna:     {len(valtozasok)}")
    print()
    print("A 20 legnagyobb átrendeződés:")
    for (honnan, hova), darab in mozgas.most_common(20):
        print(f"  {darab:5d}  {honnan[:32]:<34} -> {hova[:32]}")

    if not ir:
        print("\nPróba volt -- semmi nem íródott be. Mentés: --ir")
        return 0

    # Egyesével frissítünk, adagolt visszajelzéssel. Az `update` szűrővel
    # megy, tehát nem tud véletlenül több sort érinteni.
    hiba = 0
    for i, (hirdetes_id, szakma_id) in enumerate(valtozasok, 1):
        try:
            (db.table("hirdetesek").update({"szakma_id": szakma_id})
               .eq("id", hirdetes_id).execute())
        except Exception as e:
            hiba += 1
            if hiba <= 5:
                print(f"  Mentési hiba (hirdetés {hirdetes_id}): {e}")
        if i % 1000 == 0:
            print(f"  ... {i}/{len(valtozasok)}")

    print(f"\nMódosítva: {len(valtozasok) - hiba} hirdetés.")
    if hiba:
        print(f"FIGYELEM: {hiba} sor nem sikerült.")

    # A besorolás megváltozott, tehát a lefedettség és a cégprofil is.
    # Enélkül a piaci körkép a régi szakmákból számolna tovább.
    try:
        db.rpc("szakma_esco_parositas").execute()
        print("ESCO-párosítás frissítve.")
    except Exception as e:
        print(f"ESCO-párosítás hiba: {e}")

    print("A nézetfrissítést a pg_cron végzi (napi-karbantartas, 08:00 UTC).")
    return 1 if hiba else 0


if __name__ == "__main__":
    sys.exit(main())
