# 6. Pályaváltás és képzések

## 1. Cél és hatókör

Ez a főrész reális átjárót keres másik szakmába, majd megmutatja:

- mely meglévő készségek vihetők tovább;
- mely hiányok blokkolják vagy lassítják a váltást;
- milyen piaci esély és tanulási teher tartozik az irányhoz;
- mely képzés csökkenti ténylegesen a konkrét készséghiányt.

Nem pszichológiai diagnózist készít, és nem ígér biztos elhelyezkedést.

## 2. Bemenet és adatforrás

| Bemenet | Forrás |
|---|---|
| Megerősített készség és tapasztalat | karrierprofil |
| Preferenciák és korlátok | felhasználó |
| Teszteredmény | 5. főrész, opcionális támogató adat |
| Szakmák és feladatok | `szakmak`, `feor_lista` |
| Szakmai készségigény | hirdetések és `hirdetes_keszseg` |
| Piaci helyzet | `market_snapshots` |
| Képzésadat | `kepzesek` és ellenőrzött külső forrás |

## 3. Belső részek

1. **Target candidate builder:** lehetséges célszakmákat választ katalógusból.
2. **Transferable skill mapper:** meglévő és célkészséget kapcsol.
3. **Hard-gate evaluator:** képesítés, nyelv, hely és egyéb valódi korlát.
4. **Transition scorer:** verziózott képlettel rangsorol.
5. **Gap analyzer:** kötelező és fejleszthető hiányt különít el.
6. **Training matcher:** a gapet konkrét képzési kimenethez köti.
7. **Path builder:** lépésekre és ellenőrzési pontokra bontott utat ad.
8. **Career Advisor:** az eredményt közérthetően elmagyarázza.

Nincs külön pályaváltó vagy képzési agent.

## 4. Determinisztikus rangsorolás

### Hard gate

Kizáró vagy tisztázandó feltétel például:

- jogszabály szerint kötelező végzettség;
- kötelező engedély/tanúsítvány;
- nem teljesíthető nyelvi vagy helyi feltétel;
- a felhasználó által kizárt munkatípus;
- a megadott idő- vagy költségkeretet biztosan meghaladó minimumút.

### V1 átjárhatósági pontszám

| Komponens | Súly |
|---|---:|
| Átvihető készségek lefedettsége | 30 |
| Releváns tapasztalat és feladathasonlóság | 20 |
| Célpálya igazolt piaci kereslete | 20 |
| Készséghiány várható tanulási terhe | 15 |
| Felhasználói korlátokkal való egyezés | 10 |
| Preferencia/teszt támogató egyezése | 5 |
| **Összesen** | **100** |

A teszt legfeljebb öt ponttal befolyásolhat, így nem írhatja felül a valódi
tapasztalatot, piacot vagy korlátot.

Az eredmény három csoport:

- **közeli irány:** kevés, célzott gap;
- **hídpálya:** köztes szereppel reális;
- **hosszabb váltás:** nagyobb képzés vagy tapasztalat szükséges.

### Képzésrangsor

| Komponens | Súly |
|---|---:|
| Konkrét skill-gap lefedése | 35 |
| Szolgáltató és bizonyítvány ellenőrizhetősége | 20 |
| Időigény illeszkedése | 15 |
| Költségkeret illeszkedése | 15 |
| Formátum, hely és időbeosztás | 10 |
| Adatfrissesség | 5 |
| **Összesen** | **100** |

Szponzorált képzés nem kaphat pontelőnyt. A jelenlegi képzésadat szűkössége
látható adatkorlátként jelenik meg.

## 5. Adatmodell és API

### Entitások

- `transition_runs`: owner, profil, célbeállítás, szabályverzió.
- `transition_candidates`: célszakma, gate-ek, pontok, confidence.
- `skill_transfer_maps`: forráskészség, célkészség, kapcsolat és bizonyíték.
- `career_paths`: kiválasztott cél, mérföldkövek, státusz.
- `career_path_steps`: sorrend, típus, feltétel, becsült teher.
- `training_catalog_entries`: szolgáltató, kimenet, ár/idő ha ismert, forrás.
- `training_matches`: gap, képzés, pontbontás, frissesség.
- `user_training_choices`: mentett, kiválasztott vagy elutasított elem.

### API

| Végpont | Feladat |
|---|---|
| `POST /api/v1/transitions` | lehetséges irányok számítása |
| `GET /api/v1/transitions/{id}` | pontbontás és gap |
| `POST /api/v1/transitions/{id}/select` | felhasználói cél kiválasztása |
| `GET /api/v1/transitions/{id}/path` | mérföldköves út |
| `GET /api/v1/trainings/recommendations` | konkrét gaphez képzések |
| `POST /api/v1/trainings/{id}/save` | képzés mentése |
| `POST /api/v1/career-path/steps/{id}/complete` | saját lépés teljesítettnek jelölése |

## 6. Eszközök, jogosultságok és jóváhagyások

| Eszköz | Típus | Korlát |
|---|---|---|
| `rank_transition_paths` | determinisztikus | megerősített profil és piac |
| `calculate_skill_gaps` | determinisztikus | kanonikus készségek |
| `rank_trainings` | determinisztikus | ellenőrzött képzési rekordok |
| `explain_transition` | Career Advisor | csak számított eredményből |
| `save_career_goal` | backend | felhasználói megerősítés |
| `open_training_source` | frontend link | jelölt, ellenőrzött külső oldal |

Képzés megvásárlása vagy jelentkezés elküldése nincs automatikusan
engedélyezve. Későbbi integráció esetén külön jóváhagyási művelet.

## 7. Kimenet és Career GPS módosítása

Kimenetek:

- legfeljebb három elsődleges váltási irány;
- átvihető készségek és bizonyítékok;
- hard gate-ek, skill-gap és várható teher;
- dátumozott piaci indok;
- gaphez kötött képzési shortlist;
- mérföldköves, szerkeszthető karrierút.

GPS-események: `transition_options_ready`, `transition_path_selected`,
`training_shortlist_ready`, `training_selected`, `career_path_step_completed`.

## 8. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| Nincs reális váltási irány | őszinte eredmény és profiladat-pontosítás |
| Hiányos képzésadat | hiány látható, nincs becsült ár/idő |
| Elavult képzés | kizárás vagy egyértelmű figyelmeztetés |
| Szabályozott szakma | kötelező képesítés hard gate |
| Teszt és profil ellentmond | profil/piac elsőbbség, tisztázó kérdés |
| Kimerültség említése | együttérző, nem diagnosztizáló megfogalmazás |
| Agent túlzó ígéretet tesz | output guardrail blokkolja |

Kötelező tesztek: score-határok, gate-ek, 5%-os tesztmaximum, hiányos
képzésadat, szponzorált tartalom semlegessége és manuálisan címkézett
átjárási példák.

## 9. Frontend-megjelenés

- Három, jól elkülönített út: közeli, hídpálya, hosszabb váltás.
- Minden út kártyáján: „mit viszel magaddal”, „mi hiányzik”, piac és teher.
- Kiválasztás után jobb oldali Career GPS-idővonal épül mérföldkövekkel.
- Képzések nem általános katalógusként jelennek meg, hanem konkrét gap alatt.
- Forrás, frissítés, idő és költség csak ismert adat esetén látszik.
- Flow segít az összehasonlításban, de a döntést nem hozza meg.

## 10. Mérhető elfogadási feltételek

1. Azonos profil-, piac- és szabályverzió azonos rangsort ad.
2. Hard-gate-es szakma nem jelenhet meg közeli irányként.
3. Minden javasolt képzés legalább egy konkrét skill-gaphez kapcsolódik.
4. Teszteredmény legfeljebb a pontszám öt százalékát adja.
5. Forrás nélküli ár, idő, elhelyezkedési esély vagy szakmai követelmény nem jelenik meg.
6. A felhasználó célválasztása nélkül a GPS karriercélja nem módosul.
7. Az út és képzés vizuálisan, mobilon is összehasonlítható.
