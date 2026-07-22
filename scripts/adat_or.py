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
            f"(gyűjtés-lyuk): {lyukas_szakmak}"
        )
    if torz_szakmak:
        FIGYELEM.append(
            f"{len(torz_szakmak)} szakmánál alacsony a címkézettség "
            f"(rangsor-torzulás veszélye): {torz_szakmak}"
        )

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


if __name__ == "__main__":
    main()
