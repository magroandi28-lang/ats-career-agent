# 7. Külföldi lehetőségek

## 1. Cél és hatókör

Ez a főrész a felhasználó profiljához, nyelvtudásához, célországához és
valós mobilitási feltételeihez illő külföldi állásokat mutatja meg. Az EURES
és más engedélyezett források adatait használja, forrással és dátummal.

Nincs külön „külföldi karriertanácsadó” agent. A rangsort a 4. főrész
illesztőmotorja készíti, külföldi jogosultsági és mobilitási kapukkal. Flow és
a Career Advisor segít értelmezni.

## 2. Bemenet és adatforrás

| Bemenet | Forrás |
|---|---|
| Megerősített profil és master CV | 3. főrész |
| Nyelv és szint | igazolt/önbevallott profiladat |
| Célország és hely | felhasználó |
| Munkavállalási jogosultság | felhasználói nyilatkozat + hivatalos forráslink |
| Relokációs, remote- és időkorlát | felhasználó |
| Külföldi hirdetések | EURES és engedélyezett import |
| Készség- és állásillesztés | 4. főrész |
| Országinformáció | hivatalos, dátumozott forrás |

Jogi, adózási vagy bevándorlási követelményt LLM nem találhat ki. A rendszer
forrást mutat és bizonytalanság esetén hivatalos ellenőrzést kér.

## 3. Belső részek

1. **EURES ingestion:** ütemezett, forrásdátumos beolvasás.
2. **Foreign job normalizer:** ország, régió, nyelv, szerződés és remote mezők.
3. **Eligibility gate:** jogosultság, nyelv és kötelező helyi feltételek.
4. **Core fit engine:** ugyanaz a profilillesztés, mint a belföldi állásoknál.
5. **Mobility readiness:** relokációs és dokumentumhiányok külön értékelése.
6. **Source verifier:** hirdetés és országforrás elérhetősége/frissessége.
7. **Translation helper:** csak megértést segítő, jelölt fordítás.
8. **Foreign application adapter:** célország/nyelv szerinti dokumentumvázlat.

## 4. Determinisztikus logika és agenthatár

### Kötelező kapuk

- célország egyezik;
- hirdetés aktív és forrása elérhető;
- munkavállalási jogosultság `pass` vagy tisztázott;
- kötelező nyelvi szint teljesül;
- kötelező képesítés/tanúsítvány teljesül;
- helyszín/remote feltétel nem ütközik a felhasználói korláttal.

`Unknown` jogi vagy kötelező feltétel esetén az állás nem kerül a fő
ajánlások közé, amíg a felhasználó nem tisztázza.

### Rangsor

A szakmai `fit_score` változatlanul a 4. főrész képlete. Mellette külön
`mobility_readiness` jelenik meg:

| Mobilitási tényező | Állapot |
|---|---|
| Jogosultság | pass/fail/unknown |
| Nyelv | megfelelő/fejlesztendő/elégtelen |
| Hely és relokáció | egyezik/tisztázandó/ütközik |
| Kötelező dokumentum | kész/hiányzik/ismeretlen |
| Jelentkezési határidő | aktív/hamarosan lejár/lejárt |

A két érték nem mosható össze egy homályos „külföldi esély” százalékba.

### Agenthasználat

- Flow bekéri a hiányzó ország- és mobilitási adatot.
- Career Advisor a számított eredményt és hivatalos forrásokat magyarázza.
- Application Materials Agent lefordíthatja és célországhoz igazíthatja a
  pályázati anyagot, de új tényt nem adhat hozzá.

## 5. Adatmodell és API

### Entitások

- `foreign_job_sources`: forrás, ország, utolsó sikeres import.
- `foreign_jobs`: kanonikus job, ország, nyelv, szerződés, source URL/date.
- `foreign_job_requirements`: jogosultság, nyelv, képesítés és dokumentum.
- `mobility_profiles`: owner, országok, relokáció, jogosultsági nyilatkozat.
- `foreign_match_results`: core match, gate-ek, readiness, confidence.
- `country_reference_items`: hivatalos cím, URL, téma, ellenőrzési dátum.
- `foreign_application_packages`: job, nyelv, dokumentumok és státusz.

### API

| Végpont | Feladat |
|---|---|
| `GET /api/v1/foreign/countries` | támogatott országok és adatfrissesség |
| `PUT /api/v1/foreign/mobility-profile` | saját cél és korlát mentése |
| `POST /api/v1/foreign/matches` | személyes EURES/külföldi shortlist |
| `GET /api/v1/foreign/matches/{id}` | fit, readiness és források |
| `GET /api/v1/foreign/countries/{code}/references` | hivatalos információk |
| `POST /api/v1/foreign/applications` | célzott idegen nyelvű vázlat |

## 6. Eszközök, jogosultságok és jóváhagyások

| Eszköz | Típus | Korlát |
|---|---|---|
| `search_eures_jobs` | determinisztikus adat | friss, deduplikált rekord |
| `evaluate_foreign_eligibility` | determinisztikus | rögzített kapuk |
| `score_job_fit` | determinisztikus | 4. főrész közös motorja |
| `get_official_country_reference` | read-only adat | forrás-allowlist |
| `translate_application_draft` | Application Materials Agent | jóváhagyott alapanyag |
| `open_original_listing` | frontend link | ellenőrzött https URL |

Az alkalmazás első verziója nem küld jelentkezést automatikusan. Ha később
lesz ilyen integráció, külön előnézet és egyszeri jóváhagyás kötelező.

## 7. Kimenet és Career GPS módosítása

Kimenetek:

- legfeljebb öt fő külföldi ajánlás;
- külön szakmai illeszkedés és mobilitási készültség;
- tisztázandó jogosultságok és dokumentumok;
- eredeti hirdetés és hivatalos országforrás;
- célzott idegen nyelvű pályázati vázlat.

GPS-események: `mobility_profile_confirmed`, `foreign_shortlist_created`,
`foreign_job_selected`, `foreign_application_approved`.

## 8. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| EURES/API kiesik | utolsó snapshot csak dátummal és elavultsági jelzéssel |
| Lejárt hirdetés | kizárás a fő listából |
| Ismeretlen jogosultság | tisztázó kérdés, nincs automatikus igen |
| Hiányzó béradat | nem becsüljük meg |
| Fordítás bizonytalan | eredeti szöveg és jelölt fordítás együtt |
| Rosszindulatú hirdetésszöveg | adatként kezelve, toolhívást nem vezérel |
| Veszélyes külső URL | allowlist/protokoll-ellenőrzés, blokkolás |

Kötelező tesztek: országkód, dátum/időzóna, nyelvi gate, jogosultság
`unknown`, duplikált EURES-hirdetés, lejárt link, fordítási tényegyezés és
SSRF/rosszindulatú URL.

## 9. Frontend-megjelenés

- Ország- és nyelvválasztás Flow-val, nem hosszú beállítási oldallal.
- Kártyán zászló helyett elsődlegesen: szakmai fit, nyelv, hely, határidő,
  szerződés és forrás.
- Külön blokk: „Szakmailag illik” és „A jelentkezéshez még kell”.
- Eredeti hirdetés egy kattintással, ellenőrzött külső linken nyílik.
- Országinformáció forráskártyákon, nem LLM által írt jogi összefoglalóként.
- Flow segít összevetni a belföldi és külföldi lehetőséget.

## 10. Mérhető elfogadási feltételek

1. A külföldi szakmai fit ugyanazt a közös rangsormotort használja.
2. `Fail` vagy tisztázatlan kötelező gate nem kerül a fő shortlistbe.
3. Minden állásnak van eredeti URL-je, forrása és forrásdátuma.
4. Jogi/jogosultsági állítás hivatalos forrás nélkül nem jelenik meg tényként.
5. Fordított dokumentum szakmai állításai megegyeznek a jóváhagyott alappal.
6. Elavult EURES-snapshot egyértelműen látszik és nem nevezhető aktuálisnak.
7. Külföldi út E2E-tesztje CV-vel és CV nélkül is végigfut.
