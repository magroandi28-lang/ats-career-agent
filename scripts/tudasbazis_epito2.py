# -*- coding: utf-8 -*-
"""TUDÁSBÁZIS-ÉPÍTŐ 2. KÖR — tanácsadás + krízis + mentálhigiéné anyagok.

Andi által jóváhagyott lista (2026-07-20): saját jegyzetek + tankönyvek,
egyetemi/állami kiadványok. Kereskedelmi könyvek (Máté G., Frankl stb.)
TUDATOSAN KIHAGYVA (szerzői jog).

Futtatás:  python scripts/tudasbazis_epito2.py "<mappa1>" "<mappa2>" ...
A fájlokat az összes megadott mappában keresi (almappákban is).
Kimenet: db/tudasbazis_nyers2.json (a feltöltő mindkét nyers fájlt felküldi).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tudasbazis_epito import darabol, docx_szoveg, pdf_szoveg, pptx_szoveg, tisztit  # noqa: E402

FORRASOK2 = [
    # ── 1. kör: Andi saját jegyzetei ──
    ("Hajduska krízislélektan feldolgozása.docx", "Andi jegyzete: Hajduska krízislélektan-feldolgozás"),
    ("Tanácsadás összefoglaló.docx", "Andi jegyzete: Tanácsadás összefoglaló"),
    ("2.alkalom_Tanacsadas_modszertana_gyak_MF.docx", "Andi jegyzete: Tanácsadás módszertana gyakorlat"),
    ("Kezdő segítőként bizonytalanok vagyunk.docx", "Andi jegyzete: Kezdő segítőként"),
    ("Mit tehetünk magunkért -Varga Andrea T71V8D.docx", "Andi jegyzete: Mit tehetünk magunkért"),
    # ── 2. kör: tankönyvek, egyetemi/állami kiadványok ──
    ("Könyv Hajduska, Krizislelektan.pdf", "Hajduska: Krízislélektan"),
    ("Tanácsadás vizsághoz könyv Yvey-konyv.2005.pdf", "Ivey: Tanácsadás (2005)"),
    ("Gelsei_Megoldaskozp_tanacsadas.pdf", "Gelsei: Megoldásközpontú tanácsadás"),
    ("Korunk tudománya. Selye János. distressz nélkül. Akadémiai Kiadó Budapest.pdf",
     "Selye: Stressz distressz nélkül"),
    ("Mogyorósi-Révész Zsuzanna (2019) Érzelmi regulációs változások krízisben.pdf",
     "Mogyorósi-Révész: Érzelmi reguláció krízisben (2019)"),
    ("preventiv_mentalhigienes_gondozok_kezikonyve_pdfa.pdf",
     "Preventív mentálhigiénés gondozók kézikönyve"),
    ("Személyiség elméletek 1.pdf", "Személyiségelméletek (egyetemi jegyzet)"),
    ("tanacsadaspszich_ea.pdf", "Tanácsadás-pszichológia előadásjegyzet"),
    ("tanacsadas (1).pdf", "Tanácsadás jegyzet"),
    ("Tanacsadas_modszertana.pptx", "Dia: Tanácsadás módszertana 1"),
    ("Tanacsadas_modszertana_2.pptx", "Dia: Tanácsadás módszertana 2"),
    ("tanacsadaspszich_ea_2.pptx", "Dia: Tanácsadás-pszichológia 2"),
]


def megkeres(fajlnev: str, mappak: list):
    """A fájl megkeresése a megadott mappákban (almappákban is).
    Ékezet-kódolásra érzéketlen (NFC-normalizált összevetés)."""
    import unicodedata

    def norm(s):
        return unicodedata.normalize("NFC", s)

    cel = norm(fajlnev)
    for m in mappak:
        for gyoker, _, fajlok in os.walk(m):
            for f in fajlok:
                if norm(f) == cel:
                    return os.path.join(gyoker, f)
    return None


def main():
    mappak = sys.argv[1:] or ["."]
    kimenet = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "db", "tudasbazis_nyers2.json")
    osszes = []
    for fajl, forras_nev in FORRASOK2:
        ut = megkeres(fajl, mappak)
        if not ut:
            print(f"  KIHAGYVA (nem talalom): {fajl}")
            continue
        try:
            if fajl.lower().endswith(".pdf"):
                szoveg = pdf_szoveg(ut)
            elif fajl.lower().endswith(".docx"):
                szoveg = docx_szoveg(ut)
            elif fajl.lower().endswith(".pptx"):
                szoveg = pptx_szoveg(ut)
            else:
                continue
            szoveg = tisztit(szoveg)
            darabok = darabol(szoveg)
            for i, d in enumerate(darabok, 1):
                osszes.append({"forras": forras_nev, "resz": i, "szoveg": d})
            print(f"  OK: {forras_nev}: {len(darabok)} szakasz ({len(szoveg)} kar.)")
        except Exception as e:
            print(f"  HIBA ({fajl}): {e}")

    with open(kimenet, "w", encoding="utf-8") as f:
        json.dump(osszes, f, ensure_ascii=False, indent=1)
    print(f"\nKESZ: {len(osszes)} szakasz -> {kimenet}")


if __name__ == "__main__":
    main()
