# Az adatbázis állapota — 2026-07-30

Ez a dokumentum azt rögzíti, milyen felhasználói szolgáltatás építhető a
`karrier-ugynokseg` Supabase-projekt jelenlegi adataira.

## Jelenlegi készlet

| Adat | Darab |
|---|---:|
| Álláshirdetés | 16 503 |
| Aktív álláshirdetés | 16 118 |
| Szakma | 993 |
| ESCO-kapcsolattal rendelkező szakma | 989 |
| FEOR/KSH-kapcsolattal rendelkező szakma | 544 |
| Hirdetésből kinyert feladat vagy elvárás | 56 826 |
| Bármilyen tételes adattal rendelkező hirdetés | 15 803 |
| Ebből: feladat- vagy elvárástétellel rendelkező hirdetés | 5 740 |
| ESCO-foglalkozás | 3 039 |
| ESCO-készség | 13 939 |
| ESCO foglalkozás–készség kapcsolat | 126 051 |
| CV-szókincs-változat | 11 911 |
| Tudásanyag-szakasz | 2 735 |
| Képzés | 12 |
| Napi szakmapillanatkép | 2 947 |
| Napi cégpillanatkép | 8 402 |

Az adatok frissek: 7 781 aktív hirdetést az utolsó két napban láttunk, és
nincs 14 napnál régebben látott, még aktívként jelölt hirdetés. Az adatbázisos
`aktiv` állapot azonban nem bizonyítja, hogy a külső link még megnyitható:
élő ellenőrzés során már találtunk aktívként tárolt, de az EURES oldalán nem
megjelenő hirdetést is.

## Mennyire teljes a bér- és elvárásadat

Ez a szakasz azért van külön, mert a „részben építhető" önmagában nem mond
semmit, és mert két különböző dolgot könnyű összekeverni.

**Amit egy KONKRÉT hirdetésről tudunk** (mérve 2026-07-30, 14 653 valódi
állásra):

| | Hirdetés | Arány |
|---|---:|---:|
| Van forintban megadott béradat | 2 334 | 15,9% |
| Van feladat- vagy elvárástétel | 5 740 | 39,2% |
| Nincs hozzárendelt szakma | 2 715 | 18,5% |

**Amit egy SZAKMÁRÓL tudunk.** A `mv_szakma_lefedettseg` bizalmi szintje nem
arány, hanem szakmánkénti abszolút darabszám:

| Bizalmi szint | Kereslet | Bér | Elvárás |
|---|---|---|---|
| `eros` | ≥ 20 aktív állás | ≥ 10 béres hirdetés | ≥ 30 tétel |
| `gyenge` | ≥ 5 | ≥ 4 | ≥ 10 |
| `nincs` | ez alatt | ez alatt | ez alatt |

A 993 szakmából `eros` szinten: kereslet **137**, bér **54**, elvárás **38**.
Legalább 10 hirdetése **223** szakmának van.

**A kettőt nem szabad összemosni.** Egy „a bolti eladó bére 400–500 ezer" típusú
állítás a szakma szintjén állhat meg, mintából — miközben az adott hirdetésről
külön-külön az esetek 84%-ában semmit nem tudunk a bérről. A felhasználónak azt
kell mondani, amelyik igaz: szakmára mintát, hirdetésre csak azt, ami ott van.

Ha a szakmalista bővül, ezek az arányok esnek, mert az új szakmák kevés
hirdetéssel érkeznek — a küszöbök viszont abszolút darabszámok. Ez hígulás,
nem adatvesztés: abszolút értékben minden nőtt (kinyert tétel 52 663 → 56 826).

## Mire építhető szolgáltatás

| Szolgáltatás | Állapot | Adatbázisos alap |
|---|---|---|
| Meglévő CV ATS-kompatibilis jobb változata | építhető, az első lánc elkészült | teljes ESCO-foglalkozásleírás, kapcsolt ESCO-készségek, erős bizalmú hirdetésminták |
| Piaci körkép | építhető | aktív hirdetések, napi pillanatképek, cégszám |
| Kapcsolódó szakmák | építhető | ESCO-készségátfedés |
| Aktuális állások | a linkellenőrző és -feldúsító szolgáltatás után építhető | 16 118 aktívként tárolt link, helyszín és cégadat |
| Bérkép | részben építhető | hirdetett bér + 544 szakmánál FEOR/KSH |
| Konkrét hirdetésre szabott ATS/CV | a hirdetésfeldúsítás után építhető | EURES-részletes adat, ellenőrzött külső oldal vagy felhasználó által megadott teljes szöveg |
| Képzésajánló | még nem építhető | 12 képzés nem elegendő |
| Portfólió | későbbi szolgáltatás | a jelenlegi adatbázis önmagában nem ad projektbizonyítékot |

## A CV-szolgáltatás adatkezelési szabálya

Az adatbázis nem állíthat semmit a felhasználóról. Csak szakmai nyelvet és
piaci hátteret ad.

1. A CV-elemző kizárólag szó szerint visszakereshető forrásidézettel adhat át
   tényt.
2. A CV-író csak ezeket a tényeket fogalmazhatja újra.
3. A tényellenőrző eltávolít minden nem igazolt állítást.
4. A backend blokkol minden új számot, dátumot, URL-t vagy elérhetőséget.
5. A célmunkakör teljes ESCO-leírása és kapcsolt készségei szakmai szókincset
   adnak, de nem bizonyítják, hogy a felhasználó rendelkezik ezekkel.
6. Gyenge hirdetéslefedettségnél a hirdetésminták nem jutnak el a CV-íróhoz;
   ilyenkor csak az ESCO szakmai mag használható.

Flow a felhasználóval beszél és elindítja ezt a szolgáltatást. A backend nem
külön ágens: jogosultságot ellenőriz, lekérdez, átadást validál és állapotot
ment.

## Aktív és kerülendő adatforrások

- Aktív: `hirdetesek`, `hirdetes_tetel`, `szakmak`, `szakma_esco`,
  `esco_foglalkozas`, `esco_keszseg`, `esco_foglalkozas_keszseg`,
  `keszseg_valtozat`, napi pillanatképek.
- Régi, új szolgáltatás nem épülhet rá: `keszsegek`, `hirdetes_keszseg`,
  `v_szakma_fogalmak`, `v_szakma_keszsegek`.
- A `hirdetes_snapshot` jelenleg üres, de a sémája alkalmas a linkről
  ellenőrzött teljes hirdetésszöveg, a forrás, a tartalmi lenyomat és a
  validációs állapot tárolására. Az új hirdetésfeldúsító szolgáltatásnak ezt
  kell feltöltenie.

## A meglévő hirdetéslinkek használata

A link nem bizonyíték és nem teljes szöveg, hanem a hirdetés feldúsításának
kiindulópontja. A 2026-07-30-i ellenőrzés eredménye:

| Forrás | Linkkel tárolt hirdetés | Tárolt szöveg állapota | Teljes szöveg útja |
|---|---:|---|---|
| Jooble | 15 916 | átlagosan 259 karakteres kivonat | az eredeti munkáltatói hirdetés megkeresése; a Jooble-oldal automatizált letöltését robotvédelem blokkolhatja |
| EURES | 558 | többnyire rövid keresési leírás | a hirdetésazonosítóval lekért EURES-részletes adat vagy a dinamikus részletes oldal |
| Portál/céges | 29 | rövid kivonat | forrásspecifikus feldolgozó; blokkoláskor eredeti munkáltatói oldal keresése |

Egy adatbázisos vagy interneten talált állás csak ugyanazon a kapun keresztül
ajánlható:

1. A determinisztikus keresés kiválasztja a célmunkakör, helyszín és frissesség
   alapján megfelelő jelölteket.
2. A backend ellenőrzi a linket, követi a biztonságos átirányítást, és
   forrásspecifikus módon megszerzi a teljes szöveget.
3. A szöveg csak akkor fogadható el, ha a pozíció és a munkáltató egyezik,
   elegendően részletes, és a hirdetés még él.
4. A teljes szöveg és a lekérés bizonyítékai új `hirdetes_snapshot` rekordba
   kerülnek. Korábbi snapshotot nem írunk felül.
5. Csak az elemzésre alkalmas snapshotból készül végleges illeszkedés és
   állásajánlás.
6. Ha az adatbázisból nincs elegendő ellenőrzött találat, internetes keresés
   indul. Az internetes találat ugyanazon a mentési és validációs kapun megy
   át.
7. Ha a teljes szöveg technikailag nem szerezhető meg, a hirdetés nem kerül a
   végleges ajánlások közé. Konkrét hirdetés felhasználói linkjét Flow csak
   akkor tudja elemezni, ha a felhasználó beilleszti a szöveget.

## Működés és biztonság

- A `napi-karbantartas` cron naponta 08:00 UTC-kor fut.
- A napi gyűjtés fut: 2026-07-30-án 7 203 hirdetést láttamozott, a legutóbbi
  hirdetés 06:38 UTC-kor érkezett. Mind az 5 materializált nézet feltöltve.

### A migrációk elcsúsztak, és ezt ma semmi nem fogja meg

Mérve 2026-07-30: a repóban **50** migrációs fájl van, az éles adatbázisban
**49** fut. Az eltérés a `20260730150000_arfolyam_rls.sql` — ez a fájl bekerült
a repóba, de **nincs alkalmazva**.

Ezért igaz még mindig, hogy a `public.arfolyam` táblán nincs RLS: nem azért,
mert a döntés még hátravan, hanem mert a megírt migráció nem futott le.

**A `scripts/migracio_szinkron.py` ezt elkapná — csak épp egyetlen workflow sem
hívja meg.** A `.github/workflows/` állományaiban egyedül az `adat_or.py`
szerepel. Amíg ez így van, a migrációs eltérés csendben nő: a repó és az éles
séma külön életet él, és ez pontosan az a hibaosztály, amit a szkript
megelőzni hivatott.

Két teendő, egymástól függetlenül:

1. A hiányzó migráció alkalmazása (vagy tudatos visszavonása a repóból).
2. A `migracio_szinkron.py` bekötése a Quality workflow-ba, hogy legközelebb
   ne egy kézi ellenőrzésen múljon.
