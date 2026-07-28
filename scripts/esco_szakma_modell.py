# -*- coding: utf-8 -*-
"""A maradék szakmák ESCO-hoz rendelése modellel.

MIÉRT MODELL: a névegyezés a 96 szakmából 72-t megtalált. A maradék 24-nél
a név önmagában nem elég ("AI mérnök", "gyári operátor", "kontroller") --
tudni kell, mit jelent a szakma. Ezt kóddal nem lehet eldönteni.

MIÉRT NEM TALÁLHAT KI SEMMIT: a jelöltlistát kód állítja elő az adatbázisból,
és a modell CSAK SORSZÁMOT adhat vissza. Nem létező foglalkozást tehát
szerkezetileg képtelen visszaadni. Amit visszaad, azt még ellenőrizzük is.

MIÉRT EGYSZERI: az eredmény a `szakma_esco` táblába kerül 'modell' jelöléssel.
Utána soha többé nem kell modellt hívni ehhez -- és bármikor felülvizsgálható,
mert látszik, melyik sor honnan jött.

Futtatás:
    python scripts/esco_szakma_modell.py            # próba, nem ír
    python scripts/esco_szakma_modell.py --ir       # rögzít is
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import kliens  # noqa: E402
from utils.openai_kliens import gpt, MINOSEGI  # noqa: E402


JELOLT = 40
MIN_SZO = 4

# A rövidítéseket a szóegyezés nem tudja kezelni ("AI" két betű), pedig
# éppen ezek a legnagyobb szakmák. A feloldás determinisztikus.
ROVIDITES = {
    "ai": "mesterséges intelligencia gépi tanulás adat",
    "hr": "emberi erőforrás humán toborzás munkaügy",
    "ux": "felhasználói élmény",
    "ui": "felhasználói felület",
    "cnc": "számítógépes vezérlésű szerszámgép forgácsoló",
    "it": "információtechnológia informatika",
    "erp": "vállalatirányítási rendszer",
    "qa": "minőségbiztosítás",
}


def norm(szoveg: str) -> str:
    t = unicodedata.normalize("NFKD", (szoveg or "").lower())
    t = t.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", t)


def kereso_szavak(nev: str) -> list[str]:
    """A szakma nevéből keresőszavak, a rövidítések feloldásával."""
    szavak = norm(nev).split()
    bovitett: list[str] = []
    for sz in szavak:
        bovitett.append(sz)
        if sz in ROVIDITES:
            bovitett += norm(ROVIDITES[sz]).split()
    return [sz for sz in bovitett if len(sz) >= MIN_SZO]


# A magyar összetett szavakban a jelentés hordozója a szó VÉGÉN van:
# „háziorvos", „targoncavezető", „jelnyelvtanár". Ha csak a szó elejét
# néznénk, az „orvos" nem találná meg a „háziorvos"-t -- és pontosan ez
# hiúsította meg az első futásban az orvos, a tanár és a vízszerelő
# párosítását. Ezért a szó eleje ÉS vége is számít.
#
# A hosszküszöb védi meg a találgatástól: 5 betűnél rövidebb szórészlet
# túl sok mindenben benne van ahhoz, hogy jelentsen valamit.
MIN_OSSZETETT = 5


def egyezik(a: str, b: str) -> bool:
    if a == b:
        return True
    rovid, hosszu = (a, b) if len(a) <= len(b) else (b, a)
    if len(rovid) < MIN_OSSZETETT:
        return False
    return hosszu.startswith(rovid) or hosszu.endswith(rovid)


def _mind(db, tabla: str, mezok: str, szuro=None) -> list[dict]:
    sorok, kezdet = [], 0
    while True:
        k = db.table(tabla).select(mezok).range(kezdet, kezdet + 999)
        if szuro:
            k = szuro(k)
        adag = k.execute().data or []
        sorok += adag
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


def jeloltek(szakma: str, index: list[tuple]) -> list[tuple]:
    """Kódból előállított jelöltlista -- ez korlátozza a modellt."""
    cel = kereso_szavak(szakma)
    if not cel:
        return []
    pontozott = []
    for uri, nev, isco, cimkek in index:
        legjobb = 0.0
        for sz in cimkek:
            if not sz:
                continue
            talalt = sum(1 for c in cel if any(egyezik(c, m) for m in sz))
            if talalt:
                legjobb = max(legjobb, talalt / (len(cel) + len(sz) - talalt))
        if legjobb > 0:
            pontozott.append((legjobb, uri, nev, isco))
    pontozott.sort(reverse=True)
    return pontozott[:JELOLT]


def kerdez(szakma: str, cimek: list[str], lista: list[tuple]) -> list[int]:
    sorok = "\n".join(
        f"{i}. {nev}  (ISCO {isco or '?'})"
        for i, (_p, _u, nev, isco) in enumerate(lista)
    )
    minta = "\n".join(f"- {c}" for c in cimek[:8])
    prompt = f"""Magyar álláshirdetés-adatbázisban a(z) "{szakma}" szakmát kell
megfeleltetni az EU hivatalos ESCO foglalkozás-osztályozásának.

Így néznek ki a valódi magyar álláshirdetések erre a szakmára:
{minta}

Az ESCO-jelöltek (csak ezek közül választhatsz):
{sorok}

Feladat: add meg annak a LEGFELJEBB 3 jelöltnek a sorszámát, amelyik ezt
a munkakört képviseli.

Két eset van:

1. Van pontos megfelelő -> add meg azt az egyet.
2. A magyar szakma TÁGABB, mint bármelyik jelölt (pl. az "orvos" lefedi a
   háziorvost és a szakorvost is) -> add meg azt a 2-3 jelöltet, amelyik
   EGYÜTT a legjobban lefedi, és amelyik a magyar hirdetésekben ténylegesen
   előfordul. Ilyenkor is válassz, ne hagyd üresen.

Üres listát csak akkor adj, ha a jelöltek között tényleg NINCS semmi, ami
ehhez a munkához tartozna. A hasonló hangzás önmagában nem elég.

Válaszolj KIZÁRÓLAG JSON-nal, más szöveg nélkül:
{{"sorszamok": [0, 5], "indoklas": "egy rövid mondat"}}"""

    valasz = gpt([{"role": "user", "content": prompt}],
                 model=MINOSEGI, max_tokens=400)
    szoveg = valasz.strip()
    if "```" in szoveg:
        szoveg = szoveg.split("```")[1].removeprefix("json").strip()
    try:
        d = json.loads(szoveg)
    except json.JSONDecodeError:
        print(f"    (értelmezhetetlen válasz: {szoveg[:80]})")
        return []
    # Csak érvényes sorszám mehet tovább: a modell nem tud kitalálni URI-t,
    # de elgépelhet egy indexet.
    ki = []
    for n in d.get("sorszamok", [])[:3]:
        if isinstance(n, int) and 0 <= n < len(lista):
            ki.append(n)
    if d.get("indoklas"):
        print(f"    {d['indoklas'][:100]}")
    return ki


def main(ir: bool) -> int:
    db = kliens()
    if db is None:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    parositott = {r["szakma_id"] for r in _mind(db, "szakma_esco", "szakma_id")}
    szakmak = [s for s in _mind(db, "szakmak", "id, nev")
               if s["id"] not in parositott]
    if not szakmak:
        print("Minden szakma párosítva van.")
        return 0

    foglalkozasok = _mind(db, "esco_foglalkozas", "uri, nev, isco_kod, alt_nevek")
    index = [(f["uri"], f["nev"], f.get("isco_kod"),
              [norm(c).split() for c in [f["nev"]] + list(f.get("alt_nevek") or [])])
             for f in foglalkozasok]

    print(f"Párosítandó: {len(szakmak)} szakma | modell: {MINOSEGI}")
    print(f"Írás az adatbázisba: {'IGEN' if ir else 'NEM (próba)'}")
    print()

    uj, nincs = [], []
    for s in szakmak:
        lista = jeloltek(s["nev"], index)
        if not lista:
            print(f"{s['nev']}: nincs jelölt")
            nincs.append(s["nev"])
            continue
        cimek = [h["cim"] for h in (db.table("hirdetesek")
                 .select("cim").eq("szakma_id", s["id"]).limit(8)
                 .execute().data or [])]
        print(f"{s['nev']}  ({len(lista)} jelölt)")
        valasztott = kerdez(s["nev"], cimek, lista)
        if not valasztott:
            print("    -> NINCS megfelelő ESCO-foglalkozás")
            nincs.append(s["nev"])
            continue
        for n in valasztott:
            _p, uri, nev, isco = lista[n]
            print(f"    -> {nev}  (ISCO {isco})")
            uj.append({"szakma_id": s["id"], "foglalkozas_uri": uri,
                       "megbizhatosag": "modell"})
        print()

    print("=" * 60)
    print(f"Párosítva: {len(szakmak) - len(nincs)}/{len(szakmak)} szakma, "
          f"{len(uj)} kapcsolattal")
    if nincs:
        print(f"Nincs ESCO-megfelelő: {', '.join(nincs)}")
    if ir and uj:
        db.table("szakma_esco").upsert(
            uj, on_conflict="szakma_id,foglalkozas_uri").execute()
        print(f"Rögzítve az adatbázisba: {len(uj)} sor.")
    elif uj:
        print("Próba volt -- semmi nem íródott be. Rögzítés: --ir")
    return 0


if __name__ == "__main__":
    sys.exit(main("--ir" in sys.argv))
