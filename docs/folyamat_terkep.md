# KARRIER-ÜGYNÖKSÉG — FOLYAMAT-TÉRKÉP ÉS LOGIKAI KAPCSOLATOK

Ez a dokumentum írja le, hogyan épül fel a felhasználó útja, hol mi íródik
a profilba, és hol szól közbe Flow. A README alapja is ez lesz.

---

## 1. A FELHASZNÁLÓ ÚTJA (fő folyamat)

```
BELÉPÉS → GDPR elfogadása → Flow bemutatkozik (felugró, egyszer)
   │
   ▼
1️⃣ KARRIER ÜGYNÖK fül — a CV rendbetétele
   ├─ 🔍 Átvizsgálom: ATS-diagnózis (nem ír át)
   ├─ ✨ Átírom és pályázom: robotbarát CV + állásra szabott CV + motivációs levél
   │    (KÉZZEL ÍRT CV: lefotózva ide töltendő — a kép szöveggé íródik át!)
   └─ ✍️ Nincs CV-m: pár adatból új CV nulláról
   │
   ▼
2️⃣ KARRIER TANÁCSADÓ fül — a piac megismerése
   ├─ szakma kiválasztása → piaci körkép (készségek, bérek, KSH-átlag)
   └─ kérésre: átjárási térkép (rokon szakmák, hiányzó készségek)
   │
   ▼
3️⃣ TESZT (a Tanácsadó fül tetején, „🫶 Ismerd meg magad”)
   ├─ Holland-érdeklődés (6 állítás)
   ├─ karrierhorgony (legfontosabb + második érték)
   └─ jóllét (energia, stressz, váltás oka + szabad szöveg)
   │
   ▼
🫶 FLOW KIÉRTÉKELÉS — a teljes profilból + tudásbázisból, forrásokkal
   │
   ▼
💬 FLOW CHAT — bármikor, bármiről (tudásbázis + profil + app-ismeret)
```

Kiegészítő fülek: 🌟 Portfólió Generátor (CV → HTML-portfólió),
📚 Képzések (kurált lista), ✈️ Külföldi (még placeholder).

---

## 2. PROFIL-TÉRKÉP — ki mit ír az „egész ember” profilba

| Forrás (esemény) | Profilba kerülő adat |
|---|---|
| CV-elemzés (🔍 vagy ✨) | szakma, erősségek (meglévő kulcsszavak), ATS-illeszkedés % |
| Teszt 1. blokk | holland_tipus (érdeklődés-típus) |
| Teszt 2. blokk | karrierhorgony (első + második érték) |
| Teszt 3. blokk | jollet_jelzes (rendben / kimerülés jelei / megterhelő közeg), valtas_oka (szabad szöveggel együtt) |
| Átjárási térkép megnyitása | jel: „szakmaváltáson gondolkodik” + top 3 cél-szakma |
| CV/levél készíttetése állásra | jel: „aktív pályázás: pozíció (cég)” |
| Szakma piacának megnézése | jel: „X piaci adatait nézte” |

A profil CSAK a munkamenetben él (GDPR) — kilépéskor törlődik.

---

## 3. FLOW BEAVATKOZÁSI PONTJAI

| Helyzet | Mit tesz Flow |
|---|---|
| Első belépés | Bemutatkozik, megmutatja a 3 lépéses utat |
| Üres profil | A teljes út végigjárására hív (1️⃣→2️⃣→3️⃣) |
| Részleges profil | Pontosan megmondja, mi hiányzik még és hol találja |
| Teszt kész | Részletes kiértékelés (tudásbázis + profil, forrásokkal) |
| Kiégés / bántalmazás jele | Együttérző hang, „nem a te hibád”, szakember-ajánlás; a tanács fenntartható lépésekre vált (nem „tanulj többet”) |
| Chat-kérdés az oldalról | Pontos eligazítás (app-ismeret dokumentumból) |
| Krízis-jel a chatben | Szakember + 116-123 lelkisegély ajánlása |

---

## 4. LOGIKAI ALAPSZABÁLYOK

1. Minden állítás ADATBÓL jön (saját hirdetés-DB, KSH, tudásbázis) — az AI
   csak megfogalmaz. Bér-adatot kitalálni TILOS.
2. Váltást csak KÉRÉSRE vagy indokolt jelzésre mutatunk — nem tukmálunk.
3. Nem írjuk le, mire nincs adat — arról egyszerűen nem beszélünk
   (kivéve chat: ott őszintén jelzi, ha nincs anyaga).
4. Érzékeny állapotnál (kiégés, bántalmazás) a hangnem elsőbbséget élvez
   a tartalommal szemben.
5. A pontozás/jelzés determinisztikus kód — az AI sosem számol pontszámot.

---

## 5. MÉG BEKÖTENDŐ LOGIKÁK (fontossági sorrendben)

✅ KÉSZ: kiégés → váltás-ajánlás (prompt + cetli a kiértékelés alatt)
✅ KÉSZ: kiértékelés-frissítő gomb (bővült profilra újraszámol)
❌ ELVETVE: eltérés-észlelés — a Tanácsadó szakma-választója a megpályázott
   szakma megismerésére való, nem nézelődésre, így az összehasonlítás
   félrevezető lenne (Andi döntése, 2026-07-20).

0. **NAPI TEENDŐ, amíg el nem fogy: `python scripts/keszseg_potlo.py`** —
   ~315 hirdetés vár még készség-címkézésre (a Gemini napi keretével halad).
1. **Cetli-százalékok fogalom-szintre állítása** a Tanácsadóban (B opció,
   jóváhagyva) + készség-összevonás finomítása (C, később).
2. **Szektor-körkép** a Piaci Körkép fülre („mi nő és mi csökken az IT-ben”).
3. **Tudásbázis-bővítés:** krízis-tudásanyag életkorra/életszakaszra bontva
   + további munka- és szervezetpszichológiai források (kurálva!).
4. ✈️ Külföldi fül döntés és terv.
5. 🎤 Hang bemenet (a Streamlit felvevője bizonytalan — később saját
   komponens), 🔊 felolvasás.
6. Tudásbázis-bővítés: KRÍZIS-tudásanyag életkorra/életszakaszra bontva
   (más a pályakezdő, a középkorú váltó, az 50+ krízise) + további
   munka- és szervezetpszichológiai források. (A Delfi örökösei kikerült a tervből.)
7. Teszt-kérdéssor bővítése (teljes Holland/Schein a tankönyvből).
8. Deploy (Streamlit Cloud) + README minden fülhöz ebből a dokumentumból.

*(Ugyanilyen folyamat-térkép kell majd az Okosmérőnek is — később.)*
