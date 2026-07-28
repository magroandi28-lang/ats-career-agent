# -*- coding: utf-8 -*-
"""Megyénkénti söprés: az egész piac, nem 96 kulcsszó.

A régi gyűjtő szakmánként kérdezett (96 kulcsszó), így csak azt találta meg,
amire rákérdeztünk -- piaci körképnek ez szerkezetileg alkalmatlan.

Itt kulcsszó NÉLKÜL, megyénként lapozunk végig, és a szakmát UTÓLAG
állapítja meg a `backend.szakma_besorolo` az ESCO-nevekből.

MÉRT KORLÁT (2026-07-28): a Jooble lekérdezésenként legfeljebb ~20 oldalt
ad vissza (30/oldal = 600 hirdetés), az 50. oldal már üres. Ezért három
megyét tovább kell darabolni: Budapest (5 886), Pest (1 669),
Hajdú-Bihar (733). A többi 17 belefér.

Futtatás:
    python scripts/megye_sweep.py                 # próba, nem ír
    python scripts/megye_sweep.py --ir            # ment is
    python scripts/megye_sweep.py --megye Zala    # egy megye
"""

import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.szakma_besorolo import Besorolo  # noqa: E402
from utils.adatbazis import kliens, letezo_linkek, gyujtes_mentese  # noqa: E402


JOOBLE_URL = "https://hu.jooble.org/api/"
MAX_OLDAL = 20
VARAKOZAS = 0.4

MEGYEK = [
    "Bács-Kiskun", "Baranya", "Békés", "Borsod-Abaúj-Zemplén",
    "Csongrád-Csanád", "Fejér", "Győr-Moson-Sopron", "Heves",
    "Jász-Nagykun-Szolnok", "Komárom-Esztergom", "Nógrád", "Somogy",
    "Szabolcs-Szatmár-Bereg", "Tolna", "Vas", "Veszprém", "Zala",
]

# A 600-as korlátot túllépő megyék városokra bontva. Így ugyanaz a söprés
# mélyebbre ér, és nem kell kulcsszót visszahozni (ami torzítana).
NAGY_MEGYEK = {
    "Budapest": [f"Budapest {r}. kerület" for r in
                 ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                  "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII",
                  "XIX", "XX", "XXI", "XXII", "XXIII"]],
    "Pest": ["Érd", "Cegléd", "Vác", "Gödöllő", "Szigetszentmiklós",
             "Dunakeszi", "Budaörs", "Százhalombatta", "Monor", "Gyál",
             "Nagykőrös", "Ráckeve", "Vecsés", "Dabas", "Pest"],
    "Hajdú-Bihar": ["Debrecen", "Hajdúböszörmény", "Hajdúszoboszló",
                    "Berettyóújfalu", "Balmazújváros", "Hajdú-Bihar"],
}


def _tisztit(szoveg: str) -> str:
    szoveg = (szoveg or "").replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(szoveg.split())


def sopor(kulcs: str, helyszin: str) -> list[dict]:
    """Egy helyszín végiglapozása kulcsszó nélkül."""
    talalt: list[dict] = []
    for oldal in range(1, MAX_OLDAL + 1):
        try:
            r = requests.post(JOOBLE_URL + kulcs,
                              json={"keywords": "", "location": helyszin,
                                    "page": oldal},
                              timeout=25)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            print(f"    hiba ({helyszin}, {oldal}. oldal): {e}")
            break
        if not jobs:
            break
        for j in jobs:
            cim = _tisztit(j.get("title", ""))
            if not cim:
                continue
            talalt.append({
                "cim": cim,
                "ceg": _tisztit(j.get("company", "")),
                "snippet": _tisztit(j.get("snippet", ""))[:500],
                "link": (j.get("link") or "").strip(),
                "helyszin": _tisztit(j.get("location", "")),
                "datum": (j.get("updated") or "")[:10],
                "bersav": _tisztit(j.get("salary", "")),
                "forras_tipus": "jooble",
            })
        time.sleep(VARAKOZAS)
    return talalt


def _mind(db, tabla: str, mezok: str) -> list[dict]:
    sorok, kezdet = [], 0
    while True:
        adag = db.table(tabla).select(mezok).range(kezdet, kezdet + 999).execute().data or []
        sorok += adag
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


def main() -> int:
    kulcs = os.environ.get("JOOBLE_API_KEY")
    if not kulcs:
        print("HIBA: JOOBLE_API_KEY hiányzik.")
        return 1
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase-kapcsolat.")
        return 1

    ir = "--ir" in sys.argv
    if "--megye" in sys.argv:
        nev = sys.argv[sys.argv.index("--megye") + 1]
        helyszinek = NAGY_MEGYEK.get(nev, [nev])
    else:
        helyszinek = list(MEGYEK)
        for reszek in NAGY_MEGYEK.values():
            helyszinek += reszek

    print(f"Söprés: {len(helyszinek)} helyszín | mentés: "
          f"{'IGEN' if ir else 'NEM (próba)'}")

    print("Besoroló építése...")
    # Az angol nevek is bekerülnek: sok multi angolul hirdet, és a Zala-próbán
    # a be nem soroltak nagy része angol című volt. Az ESCO ugyanarra az
    # URI-ra adja mindkét nyelvet, tehát a találat ugyanoda vezet.
    foglalkozasok = _mind(
        db, "esco_foglalkozas", "uri, nev, isco_kod, alt_nevek, nev_en, alt_nevek_en")
    for f in foglalkozasok:
        # A `nev_en` külön marad: az a hivatalos angol név, és a besoroló
        # erősebbnek veszi az alternatíváknál.
        f["alt_nevek"] = (list(f.get("alt_nevek") or [])
                          + list(f.get("alt_nevek_en") or []))

    besorolo = Besorolo(
        foglalkozasok,
        _mind(db, "szakmak", "id, nev"),
        _mind(db, "szakma_esco", "szakma_id, foglalkozas_uri"),
    )

    egyedi: dict[str, dict] = {}
    for i, hely in enumerate(helyszinek, 1):
        adag = sopor(kulcs, hely)
        uj = sum(1 for a in adag if a["link"] and a["link"] not in egyedi)
        for a in adag:
            if a["link"]:
                egyedi.setdefault(a["link"], a)
        print(f"[{i:3d}/{len(helyszinek)}] {hely:28s} {len(adag):5d} találat, "
              f"{uj:5d} új a söprésben")

    print()
    print(f"Egyedi hirdetés a söprésben: {len(egyedi)}")

    megvan = letezo_linkek(list(egyedi))
    ujak = [a for a in egyedi.values() if a["link"] not in megvan]
    print(f"Ebből még nincs az adatbázisban: {len(ujak)}")

    # Láttamozás: amit most is látunk, az él. Enélkül nem tudnánk
    # megkülönböztetni a nyitott állást a betöltöttől -- fél év múlva a
    # piaci körkép halott hirdetésekből számolna.
    if ir and megvan:
        latott, linkek = 0, list(megvan)
        for i in range(0, len(linkek), 500):
            try:
                v = db.rpc("hirdetes_lattam",
                           {"linkek": linkek[i:i + 500]}).execute()
                latott += v.data or 0
            except Exception as e:
                print(f"Láttamozási hiba: {e}")
        print(f"Láttamozva (még él): {latott}")

    # Besorolás
    csoport: dict[tuple[str, str], list[dict]] = defaultdict(list)
    besorolatlan: list[str] = []
    uj_szakma: Counter = Counter()
    for a in ujak:
        t = besorolo.besorol(a["cim"])
        if t is None:
            besorolatlan.append(a["cim"])
            continue
        if t.szakma_id is None:
            uj_szakma[t.szakma_nev] += 1
        csoport[(t.szakma_nev, t.kategoria or "Egyéb")].append(a)

    print(f"Besorolva: {len(ujak) - len(besorolatlan)}/{len(ujak)} "
          f"({len(csoport)} különböző szakma)")
    print(f"Ebből ÚJ szakma, ami eddig nem volt: {len(uj_szakma)}")
    for nev, db_ in uj_szakma.most_common(15):
        print(f"    {db_:4d}  {nev}")
    if besorolatlan:
        print(f"Nem besorolható: {len(besorolatlan)}, például:")
        for c in besorolatlan[:5]:
            print(f"    {c[:70]}")

    if not ir:
        print()
        print("Próba volt -- semmi nem íródott be. Mentés: --ir")
        return 0

    mentve = 0
    for (szakma, kategoria), allasok in csoport.items():
        try:
            mentve += gyujtes_mentese(
                {"szakma": szakma, "szakma_kategoria": kategoria}, allasok)
        except Exception as e:
            print(f"Mentési hiba ({szakma}): {e}")
    print(f"\nMentve: {mentve} új hirdetés.")

    # A most felfedezett szakmáknak még nincs ESCO-kapcsolatuk, pedig épp
    # az ESCO nevéről kapták a nevüket. Enélkül lenne hirdetésük, de nem
    # tudnánk semmit mondani arról, mi tartozik a szakmához.
    try:
        valasz = db.rpc("szakma_esco_parositas").execute()
        print(f"Új ESCO-kapcsolat: {valasz.data}")
    except Exception as e:
        print(f"ESCO-párosítás hiba: {e}")

    # A lejáratozás belefér a REST időkorlátjába, ezért itt fut: így a
    # söprés után azonnal helyes az "aktív" hirdetések száma.
    try:
        valasz = db.rpc("hirdetes_lejarat", {"napok": 14}).execute()
        print(f"Eltűntnek jelölve: {valasz.data}")
    except Exception as e:
        print(f"Lejáratozási hiba: {e}")

    # A tudásanyag-címkézés és a nézetfrissítés NEM innen megy: a Supabase
    # REST-végpontja 8 másodpercnél elvágja, és csendben kimaradna. Azokat a
    # `napi_karbantartas()` végzi, amit a pg_cron futtat 05:30 UTC-kor --
    # az adatbázison belül, időkorlát nélkül, a gyűjtéstől függetlenül.
    print("A nézetfrissítést a pg_cron végzi (napi-karbantartas, 05:30 UTC).")

    print("A tételek kinyerése külön lépés: scripts/hirdetes_tetel_feltolto.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
