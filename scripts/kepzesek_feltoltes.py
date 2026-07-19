# -*- coding: utf-8 -*-
"""A kurált képzéslistát (agents/kepzes_db.py) feltölti a Supabase
'kepzesek' táblájába. Egyszer futtatod; később a Supabase Table
Editorban kézzel is bővítheted a képzéseket, kód nélkül.

Futtatás a projekt gyökeréből:
    python scripts/kepzesek_feltoltes.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.kepzes_db import KEPZES_DB  # noqa: E402
from utils.adatbazis import kliens      # noqa: E402


def main():
    db = kliens()
    if db is None:
        print("HIBA: Supabase kapcsolat nincs beallitva (.env)!")
        return

    sorok = []
    for terulet, lista in KEPZES_DB.items():
        for k in lista:
            sorok.append({
                "terulet": terulet,
                "nev": k.get("nev", ""),
                "szolgaltato": k.get("szolgaltato", ""),
                "link": k.get("link", ""),
                "idotartam": k.get("idotartam", ""),
                "ar": k.get("ar", ""),
                "miert_jo": k.get("miert_jo", ""),
            })

    db.table("kepzesek").upsert(sorok, on_conflict="nev").execute()
    print(f"KESZ! {len(sorok)} kepzes feltoltve a Supabase-be.")


if __name__ == "__main__":
    main()
