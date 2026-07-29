# -*- coding: utf-8 -*-
"""ADATŐR — teljes adatminőség-vizsgálat, determinisztikusan, 0 Ft.

Minden táblát végignéz, és érthető jelentést ír: mit talált, miért baj.
CSAK JELENT, semmit nem töröl — a javítás mindig külön döntés!

Futtatás:  python scripts/adat_or.py
Ajánlott: hetente, illetve minden nagyobb gyűjtés/bővítés után.
"""

import datetime
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402

HIBA = []      # súlyos: felhasználó is észreveheti
FIGYELEM = []  # érdemes rendezni, de nem éget


def _rovid(elemek, darab: int = 8) -> str:
    """Egy napi jelentés, amit nem lehet elolvasni, nem jelentés.

    A régi változat több száz elemet öntött egyetlen sorba -- a lényeg
    elveszett a felsorolásban.
    """
    elemek = list(elemek)
    if len(elemek) <= darab:
        return str(elemek)
    return f"{elemek[:darab]} … és még {len(elemek) - darab}"


def lapozva(db, tabla, mezok):
    sorok, start = [], 0
    while True:
        r = db.table(tabla).select(mezok).range(start, start + 999).execute()
        adag = r.data or []
        sorok.extend(adag)
        if len(adag) < 1000:
            break
        start += 1000
    return sorok


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    print("=" * 60)
    print("ADATŐR — adatminőség-jelentés")
    print("=" * 60)

    # ── 1. SZAKMÁK ───────────────────────────────────────────
    szakmak = lapozva(db, "szakmak", "id, nev")
    print(f"\n[1] SZAKMÁK ({len(szakmak)} sor)")
    print("    Ellenőrzés: kis/nagybetű-duplikátum (ugyanaz a szakma két sorban")
    print("    = kettéhasadó statisztika, ellentmondó kategóriák a Körképen)")
    csop = defaultdict(list)
    for s in szakmak:
        csop[s["nev"].strip().lower()].append(s["nev"])
    duplak = {k: v for k, v in csop.items() if len(v) > 1}
    if duplak:
        HIBA.append(f"szakma-duplikátum: {list(duplak.values())}")
    print("    Ellenőrzés: rokonnév-gyanú (pl. 'raktáros' ~ 'raktári kisegítő'")
    print("    = a felhasználó két helyen látja ugyanazt a piacot)")
    nevek = [s["nev"] for s in szakmak]
    rokonok = []
    for i, a in enumerate(nevek):
        for b in nevek[i + 1:]:
            ta = {w[:5] for w in re.findall(r"\w+", a.lower()) if len(w) > 4}
            tb = {w[:5] for w in re.findall(r"\w+", b.lower()) if len(w) > 4}
            if ta and tb and (ta & tb):
                rokonok.append(f"{a} ~ {b}")
    if rokonok:
        FIGYELEM.append(f"rokonnév-gyanú ({len(rokonok)}): {rokonok[:5]}")

    # ── 2. HIRDETÉSEK ────────────────────────────────────────
    hirdetesek = lapozva(db, "hirdetesek", "id, cim, ceg_id, szakma_id, link, bersav")
    print(f"\n[2] HIRDETÉSEK ({len(hirdetesek)} sor)")
    print("    Ellenőrzés: üres cím / hiányzó szakma / hiányzó link")
    ures_cim = sum(1 for h in hirdetesek if not (h.get("cim") or "").strip())
    nincs_szakma = sum(1 for h in hirdetesek if not h.get("szakma_id"))
    nincs_link = sum(1 for h in hirdetesek if not (h.get("link") or "").strip())
    if ures_cim:
        HIBA.append(f"{ures_cim} hirdetésnek nincs címe")
    if nincs_szakma:
        FIGYELEM.append(f"{nincs_szakma} hirdetés szakma nélkül (nem számít bele semmibe)")
    if nincs_link:
        FIGYELEM.append(f"{nincs_link} hirdetés link nélkül (dedup nem védi)")
    print("    Ellenőrzés: link-duplikátum (ugyanaz az állás kétszer = torz számok)")
    linkek = defaultdict(int)
    for h in hirdetesek:
        if h.get("link"):
            linkek[h["link"]] += 1
    linkdup = sum(1 for v in linkek.values() if v > 1)
    if linkdup:
        HIBA.append(f"{linkdup} duplikált link a hirdetésekben")

    # ── 3. CÉGEK ─────────────────────────────────────────────
    cegek = lapozva(db, "cegek", "id, nev")
    print(f"\n[3] CÉGEK ({len(cegek)} sor)")
    print("    Ellenőrzés: névvariánsok (pl. 'Bosch' / 'Bosch Kft.' / 'BOSCH'")
    print("    = a Körkép 'hány cég keres' száma felfelé torzul)")
    cnev = defaultdict(list)
    for c in cegek:
        kulcs = re.sub(r"\b(kft|zrt|bt|nyrt|ltd|gmbh)\.?\b", "",
                       (c["nev"] or "").lower()).strip(" .,")
        cnev[kulcs].append(c["nev"])
    cegdup = {k: v for k, v in cnev.items() if len(v) > 1 and k}
    if cegdup:
        FIGYELEM.append(f"cég-névvariáns ({len(cegdup)} csoport): "
                        f"{list(cegdup.values())[:3]}")

    # ── 4. KÉSZSÉGEK ─────────────────────────────────────────
    keszsegek = lapozva(db, "keszsegek", "id, nev, kanonikus")
    print(f"\n[4] KÉSZSÉGEK ({len(keszsegek)} sor)")
    print("    Ellenőrzés: kanonikus név nélküliek (nem vonódnak össze a")
    print("    statisztikában = széttöredezett, kicsi százalékok)")
    nincs_kanon = sum(1 for k in keszsegek if not k.get("kanonikus"))
    if nincs_kanon:
        FIGYELEM.append(f"{nincs_kanon} készség kanonikus név nélkül "
                        f"(futtasd: scripts/keszseg_tisztitas.py)")
    print("    Ellenőrzés: gyanúsan hosszú/mondatszerű készségnevek")
    hosszu = [k["nev"] for k in keszsegek if len(k.get("nev") or "") > 60]
    if hosszu:
        FIGYELEM.append(f"{len(hosszu)} túl hosszú készségnév, pl.: {hosszu[:2]}")

    # ── 5. KAPCSOLATOK ───────────────────────────────────────
    kapcsolatok = lapozva(db, "hirdetes_keszseg", "hirdetes_id, keszseg_id")
    print(f"\n[5] HIRDETÉS–KÉSZSÉG KAPCSOLATOK ({len(kapcsolatok)} sor)")
    print("    Ellenőrzés: hirdetések készség-címke nélkül (láthatatlanok a")
    print("    Tanácsadó statisztikáiban)")
    cimkezett = {k["hirdetes_id"] for k in kapcsolatok}
    cimketlen = sum(1 for h in hirdetesek if h["id"] not in cimkezett)
    if cimketlen:
        FIGYELEM.append(f"{cimketlen} hirdetés készség-címke nélkül "
                        f"(futtasd: scripts/keszseg_potlo.py)")

    # ── 6. TUDÁSBÁZIS ────────────────────────────────────────
    tudas = lapozva(db, "tudasanyag", "id, forras, szoveg")
    print(f"\n[6] TUDÁSBÁZIS ({len(tudas)} szakasz)")
    print("    Ellenőrzés: duplikált szöveg (kétszer feltöltött anyag) +")
    print("    zaj-minták (tartalomjegyzék, számhalom)")
    latott, tdup = set(), 0
    for t in tudas:
        uj = hash(t["szoveg"])
        if uj in latott:
            tdup += 1
        latott.add(uj)
    if tdup:
        HIBA.append(f"{tdup} duplikált tudás-szakasz")
    zaj = 0
    for t in tudas:
        sz = t["szoveg"]
        if sz.count(".") / max(len(sz), 1) > 0.2 or \
           sum(1 for c in sz if c.isalpha()) / max(len(sz), 1) < 0.5:
            zaj += 1
    if zaj:
        FIGYELEM.append(f"{zaj} zajgyanús tudás-szakasz "
                        f"(futtasd: scripts/tudas_zajszuro.py)")
    ures_emb = db.table("tudasanyag").select("id", count="exact") \
                 .is_("embedding", "null").execute().count
    if ures_emb:
        HIBA.append(f"{ures_emb} tudás-szakasznak nincs embeddingje (nem kereshető)")

    # ── 7. SZAKMÁNKÉNTI GYŰJTÉS-EGÉSZSÉG ÉS CÍMKÉZETTSÉG ─────
    print(f"\n[7] SZAKMÁNKÉNTI GYŰJTÉS ÉS CÍMKÉZETTSÉG")
    print("    Ellenőrzés: van-e szakma, ahol 7 napja nem jött be új hirdetés")
    print("    (gyűjtés-lyuk — érdemes új forrást keresni hozzá), és hol")
    print("    alacsony a címkézettség (torz rangsor: jó találatok tűnhetnek")
    print("    0%-osnak, mert nincs elmentve hozzájuk készség-adat)")

    szakma_nev_map = {s["id"]: s["nev"] for s in szakmak}
    hirdetesek_reszletes = lapozva(db, "hirdetesek", "id, szakma_id, letrehozva")

    het_hatara = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=7)).isoformat()

    uj_7nap = defaultdict(int)
    osszes_szakmankent = defaultdict(int)
    cimzett_szakmankent = defaultdict(int)

    for h in hirdetesek_reszletes:
        sz_id = h.get("szakma_id")
        if not sz_id:
            continue
        osszes_szakmankent[sz_id] += 1
        if h["id"] in cimkezett:
            cimzett_szakmankent[sz_id] += 1
        if (h.get("letrehozva") or "") >= het_hatara:
            uj_7nap[sz_id] += 1

    lyukas_szakmak = []
    torz_szakmak = []
    for sz_id, nev in szakma_nev_map.items():
        ossz = osszes_szakmankent.get(sz_id, 0)
        if ossz == 0:
            continue  # sose volt hozzá hirdetés -- ez más probléma, nem gyűjtés-lyuk
        if uj_7nap.get(sz_id, 0) == 0:
            lyukas_szakmak.append(nev)
        cimzett = cimzett_szakmankent.get(sz_id, 0)
        if (cimzett / ossz) < 0.7:
            torz_szakmak.append(f"{nev} ({round(100 * cimzett / ossz)}% címkézett)")

    if lyukas_szakmak:
        FIGYELEM.append(
            f"{len(lyukas_szakmak)} szakmánál 7 napja nincs új hirdetés "
            f"(gyűjtés-lyuk): {_rovid(lyukas_szakmak)}"
        )
    # A címkézettség a `hirdetes_keszseg` táblából számol, amit a
    # `hirdetes_tetel` leváltott, és a napi karbantartása 2026-07-29-én
    # megszűnt. Az arány innentől szükségszerűen romlik, tehát figyelmeztetni
    # rá félrevezető: nem a gyűjtés hibája, hanem egy szándékos leállítás
    # következménye. A jelentésben marad, de tényként, nem riasztásként.
    if torz_szakmak:
        print(f"\n    (Tájékoztató: {len(torz_szakmak)} szakmánál alacsony a "
              f"régi készség-címkézettség. Ez a leállított `hirdetes_keszseg` "
              f"tábla maradványa, nem gyűjtési hiba.)")

    # ── BESOROLÁS-MINŐSÉG ────────────────────────────────────
    #
    # MIÉRT VAN EZ ITT: 2026-07-29-én 174 teszt volt zöld, miközben az „AI
    # mérnök" szakma leggyakoribb hirdetése „Konyhai kisegítő" volt, a
    # „szoftvertesztelő" 517 hirdetéséből pedig 61 szólt tesztelésről. Ezt
    # semmi nem jelezte -- kézzel kellett észrevenni, napok múlva.
    #
    # Két mérce, mindkettő kézi címkézés nélkül:
    #
    # 1. ÖNKONZISZTENCIA: ha a cím egy szakma NEVE, annak a szakmának kell
    #    kijönnie. A szakmanevek maguk adják az elvárt eredményt.
    # 2. CÍMILLESZKEDÉS: a nagy szakmákban a tárolt hirdetéscímek hány
    #    százaléka sorolódna ma ugyanabba a szakmába. Ha egy szakma tele van
    #    olyan hirdetéssel, aminek a címe máshová vezet, akkor a szakma
    #    gyűjtőhellyé vált -- és a piaci körkép róla hamis bért mutat.
    print("\n--- BESOROLÁS-MINŐSÉG ---")
    from backend.szakma_besorolo import Besorolo  # noqa: E402

    foglalkozasok = lapozva(
        db, "esco_foglalkozas",
        "uri, nev, isco_kod, alt_nevek, nev_en, alt_nevek_en")
    for f in foglalkozasok:
        f["alt_nevek"] = (list(f.get("alt_nevek") or [])
                          + list(f.get("alt_nevek_en") or []))
    szakma_sorok = lapozva(db, "szakmak", "id, nev")
    besorolo = Besorolo(
        foglalkozasok, szakma_sorok,
        lapozva(db, "szakma_esco", "szakma_id, foglalkozas_uri"))

    ONKONZISZTENCIA_KUSZOB = 95.0
    talalt = 0
    eltero = []
    for s in szakma_sorok:
        t = besorolo.besorol(s["nev"])
        if t is not None and t.szakma_id == s["id"]:
            talalt += 1
        else:
            eltero.append(f"{s['nev']} -> {t.szakma_nev if t else '(nincs)'}")
    arany = 100.0 * talalt / max(len(szakma_sorok), 1)
    print(f"Önkonzisztencia: {talalt}/{len(szakma_sorok)} ({arany:.1f}%)")
    if arany < ONKONZISZTENCIA_KUSZOB:
        HIBA.append(
            f"A besoroló önkonzisztenciája {arany:.1f}% "
            f"(küszöb {ONKONZISZTENCIA_KUSZOB}%). Példák: {eltero[:5]}"
        )

    # Címilleszkedés csak ott értelmes, ahol van elég hirdetés.
    CIMILLESZKEDES_KUSZOB = 50.0
    MIN_HIRDETES = 50
    cimek_szakmankent = defaultdict(list)
    for h in lapozva(db, "hirdetesek", "cim, szakma_id"):
        if h.get("szakma_id"):
            cimek_szakmankent[h["szakma_id"]].append(h.get("cim") or "")

    szakma_nev = {s["id"]: s["nev"] for s in szakma_sorok}
    gyujtohelyek = []
    for sz_id, cimek in cimek_szakmankent.items():
        if len(cimek) < MIN_HIRDETES:
            continue
        egyezo = sum(
            1 for c in cimek
            if (lambda t: t is not None and t.szakma_id == sz_id)(
                besorolo.besorol(c))
        )
        szazalek = 100.0 * egyezo / len(cimek)
        if szazalek < CIMILLESZKEDES_KUSZOB:
            gyujtohelyek.append(
                (szazalek, f"{szakma_nev.get(sz_id, sz_id)} "
                           f"({egyezo}/{len(cimek)} = {szazalek:.0f}%)"))

    gyujtohelyek.sort()
    if gyujtohelyek:
        print(f"Gyűjtőhellyé vált szakma: {len(gyujtohelyek)}")
        for _sz, leiras in gyujtohelyek[:10]:
            print(f"   {leiras}")
        HIBA.append(
            f"{len(gyujtohelyek)} szakmánál a hirdetéscímek kevesebb mint "
            f"{CIMILLESZKEDES_KUSZOB:.0f}%-a vezet ugyanoda -- a piaci körkép "
            f"róluk téves bért és elvárást mutat. "
            f"Legrosszabbak: {_rovid([l for _s, l in gyujtohelyek], 5)}"
        )
    else:
        print("Nincs gyűjtőhellyé vált szakma.")

    # ── ÖSSZEGZÉS ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ÖSSZEGZÉS")
    print("=" * 60)
    if not HIBA and not FIGYELEM:
        print("✅ Minden ellenőrzés tiszta — az adatbázis rendben van!")
    if HIBA:
        print(f"\n❌ SÚLYOS ({len(HIBA)}) — ezt a felhasználó is észreveheti:")
        for h in HIBA:
            print(f"   - {h}")
    if FIGYELEM:
        print(f"\n⚠️ FIGYELEM ({len(FIGYELEM)}) — érdemes rendezni:")
        for f in FIGYELEM:
            print(f"   - {f}")

    # HIBÁS KILÉPÉSI KÓD SÚLYOS TALÁLATNÁL.
    #
    # Enélkül az adatőr csak beszél: a napi futás zölden zárul, a jelentést
    # senki nem olvassa el, és a hiba hetekig bent marad. Pontosan ez történt
    # a besorolással -- kézzel kellett észrevenni.
    #
    # A FIGYELEM nem állít meg semmit: az rendezendő, nem éget.
    return 1 if HIBA else 0


if __name__ == "__main__":
    sys.exit(main())
