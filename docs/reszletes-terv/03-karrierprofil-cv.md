# 3. Karrierprofil és CV

> **Kanonikus elsőbbség:** a CV-feltöltésből induló felhasználói utaknál és az
> ATS indítási feltételeinél a
> [felhasználói állapotgép](../felhasznaloi-allapotgep.md) az irányadó.

## 1. Cél és hatókör

Ez a főrész hozza létre a rendszer hiteles személyes alapját: a verziózott
karrierprofilt és a master CV-t.

Két egyenrangú belépés van:

- meglévő CV feltöltése és ellenőrzött feldolgozása;
- CV nélküli, rövid, Flow által vezetett profilépítés.

Itt még nem egy konkrét állásra készül az anyag. Az állásra szabott CV és
motivációs levél a 4. főrész feladata.

## 2. Bemenet és adatforrás

| Bemenet | Forrás | Feldolgozás |
|---|---|---|
| PDF/DOCX/kép | felhasználó | biztonsági ellenőrzés, szövegkinyerés, jelöltek |
| Szakmai válasz | Flow-interjú | mezőnkénti validálás és megerősítés |
| Projekt/link | felhasználó | URL-ellenőrzés, tulajdonosi állítás, későbbi portfóliókapcsolat |
| Készségfogalom | meglévő `keszsegek` | kanonikus azonosító és szinonima |
| Szakma/FEOR | `szakmak`, `feor_lista` | cél és szakmai kategória |
| Korábbi profilverzió | Supabase | módosítási előzmény és visszaállítás |

## 3. Belső részek

1. **Dokumentumfeldolgozó:** szöveget és oldalszerkezetet nyer ki.
2. **Profilkivonatoló:** strukturált tényjelölteket készít.
3. **Evidence mapper:** minden tényt dokumentumrészhez vagy válaszhoz köt.
4. **Készség-normalizáló:** szinonimát kanonikus készséghez kapcsol.
5. **Duplikációkezelő:** azonos tapasztalatot és készséget összevonási javaslatként ad.
6. **Profil-review:** bizonytalan vagy ellentmondó tényt a felhasználó elé tesz.
7. **Snapshot service:** csak megerősített adatokból új profilverziót készít.
8. **Master CV builder:** a megerősített profilból semleges alap-CV-t készít.

## 4. Determinisztikus logika és agenthatár

### Determinisztikus

- fájl- és szövegellenőrzés;
- dátumformátum, időszakütközés és kötelező mezők;
- bizonyíték meglétének ellenőrzése;
- készségazonosító, nyelvi szint és szakmakód normalizálása;
- profilverzió, változáslista és teljességi állapot;
- PDF/DOCX export technikai előállítása.

### LLM használata

LLM csak **tényjelölteket** vonhat ki a CV szövegéből, illetve közérthetően
fogalmazhat. Kimenete strukturált, és minden mezőhöz tartalmaz:

```text
CandidateFact
  field_type
  value
  source_span
  confidence
  normalization_candidate
```

A jelölt nem válik igazolt profilténnyé automatikusan. Alacsony bizonyosság,
hiányzó forrás vagy ütközés esetén felhasználói döntés kötelező.

CV nélküli profilnál Flow kérdez, de az orchestrator határozza meg a hiányzó
mezőket. Flow nem „ismeri meg” a felhasználót olyan tényből, amelyet a
felhasználó nem adott meg vagy nem erősített meg.

## 5. Adatmodell és API

### Entitások

- `career_profiles`: owner, aktív snapshot, célállapot.
- `career_profile_snapshots`: verzió, teljesség, létrehozási ok.
- `profile_experiences`: szerep, szervezet, időszak, feladatok, evidence.
- `profile_educations`: képzés, intézmény, szint, időszak, evidence.
- `profile_skills`: kanonikus skill, szint, év, utolsó használat, evidence.
- `profile_languages`: nyelv, szint, bizonyíték vagy önbevallás.
- `profile_projects`: projektalapadat, szerep, eredmény, link, evidence.
- `career_goals`: célpozíció, iparág, hely, munkamód, korlátok.
- `user_documents`: privát storage-hivatkozás, típus, státusz, hash.
- `document_extractions`: parserverzió, jelöltek, hibák, minőség.
- `profile_fact_evidence`: tény és pontos forráshivatkozás.

### API

| Végpont | Feladat |
|---|---|
| `POST /api/v1/profile/import` | biztonságos CV-import indítása |
| `GET /api/v1/profile/imports/{id}` | kivonatolás állapota és jelöltjei |
| `POST /api/v1/profile/facts/review` | jelöltek elfogadása, javítása vagy elutasítása |
| `GET /api/v1/profile` | aktív, strukturált profil |
| `PATCH /api/v1/profile/draft` | saját vázlat mezőinek módosítása |
| `POST /api/v1/profile/confirm` | új megerősített snapshot létrehozása |
| `GET /api/v1/profile/versions` | verziók és változáslista |
| `POST /api/v1/cv/master/draft` | semleges master CV vázlata |
| `GET /api/v1/cv/master/{id}/export` | jóváhagyott PDF/DOCX export |

## 6. Eszközök, jogosultságok és jóváhagyások

| Művelet | Végrehajtó | Feltétel |
|---|---|---|
| Dokumentum olvasása | parser | tulajdonos, tiszta fájl |
| Tényjelöltek készítése | extraction service | szűkített dokumentumszöveg |
| Profiltény mentése | profile service | felhasználói megerősítés vagy közvetlen saját bevitel |
| Master CV szövegezése | Application Materials Agent | csak megerősített profil |
| Profilverzió aktiválása | profile service | változás-előnézet elfogadása |
| CV export | renderer | jóváhagyott vázlat |

Agent csak a szükséges profilmezőket kapja, eredeti teljes dokumentumot
alapból nem.

## 7. Kimenet és Career GPS módosítása

Kimenetek:

- megerősített `CareerProfileSnapshot`;
- hiányzó vagy bizonytalan mezők listája;
- bizonyítékkal ellátott készség- és tapasztalatlista;
- semleges master CV;
- profilváltozás és verziótörténet.

GPS-esemény csak ezeknél:

- `profile_draft_created`;
- `profile_fact_confirmed`;
- `profile_snapshot_activated`;
- `master_cv_approved`.

„Profil kész” csak akkor jelenhet meg, ha a célhoz szükséges minimumadatok
megerősítettek. Az általános profil teljessége és az adott célhoz való
alkalmasság külön fogalom.

## 8. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| Olvashatatlan CV | oldal- és hibahely megjelölése, kézi bevitel lehetősége |
| OCR-bizonytalanság | eredeti részlet és jelölt egymás mellett |
| Ellentmondó dátum | nem menthető megerősítettként döntés nélkül |
| Ismeretlen készség | új, felhasználói címke; későbbi kanonizálás |
| CV-ben lévő prompt injection | szövegként tárolódik, toolt nem indíthat |
| Másik user dokumentuma | RLS és signed URL megtagadja |
| Érzékeny adat | alapból nem szükséges mezőként jelölve, exportból kihagyható |

Kötelező tesztek: többhasábos CV, kép-PDF, hibás Unicode, magyar/angol vegyes
CV, ismétlődő tapasztalat, hiányos dátum, rosszindulatú utasítás és nagy fájl.

## 9. Frontend-megjelenés

### Meglévő CV

1. Feltöltés egyetlen gombbal.
2. Feldolgozás után kétoszlopos review: eredeti részlet és kivont adat.
3. Bizonytalan mező sárga, ellentmondás piros, megerősített zöld jelölést kap.
4. „Profil létrehozása” csak az ellenőrzés végén aktív.

### CV nélkül

Flow egyszerre egy rövid, értelmes kérdést tesz fel. A jobb oldali GPS-en
látható, mely profilrészek épültek fel. Nem hosszú űrlappal indul.

### Profilszerkesztő

Tapasztalat, készség, végzettség, nyelv, projekt és cél külön szerkeszthető.
Minden tény mellett látszik: igazolt, önbevallás vagy ellenőrzendő.

## 10. Mérhető elfogadási feltételek

1. Kivont CV-adat felhasználói megerősítés nélkül nem kerül igazolt profilba.
2. Minden rangsorolásban használt profiltényhez létezik evidence vagy
   kifejezett önbevallás.
3. Profilverzió visszaállítható, a változások mezőnként láthatók.
4. Master CV nem tartalmaz a profilban nem szereplő szakmai állítást.
5. Importhibánál a felhasználó kézi úton folytathatja, adatvesztés nélkül.
6. CV-vel és CV nélkül is elkészíthető a minimumprofil E2E-tesztben.
7. Másik felhasználó profilja, CV-je és signed URL-je nem érhető el.
