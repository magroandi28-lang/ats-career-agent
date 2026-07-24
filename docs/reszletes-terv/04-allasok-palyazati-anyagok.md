# 4. Állások és pályázati anyagok

> **Kanonikus elsőbbség:** az álláskeresés, álláskiválasztás, ATS,
> pályázati munkapéldány, beadás és emberi jóváhagyás felhasználói folyamatánál
> a [felhasználói állapotgép](../felhasznaloi-allapotgep.md) az irányadó.

## 1. Cél és hatókör

Ez a főrész a megerősített karrierprofilhoz legjobban illő, reálisan
megpályázható állásokat választja ki, majd a felhasználó által kiválasztott
álláshoz ATS-elemzést, célzott CV-t és motivációs levelet készít.

A sorrend kötelező:

1. megerősített profil vagy master CV;
2. állásillesztés és shortlist;
3. felhasználó kiválaszt egy állást;
4. ATS-összevetés;
5. célzott, de kizárólag valós állításokat tartalmazó pályázati anyag.

## 2. Bemenet és adatforrás

| Bemenet | Forrás |
|---|---|
| Profil és karriercél | aktív `CareerProfileSnapshot` |
| Álláshirdetés | `hirdetesek`, Jooble és más ellenőrzött import |
| Követelménykészségek | `hirdetes_keszseg`, `keszsegek` |
| Cégadat | `cegek` |
| Master CV | 3. főrész |
| Felhasználói korlát | hely, remote, nyelv, bér ha ismert, munkavállalási feltétel |

Elavult, forrás nélküli vagy duplikált hirdetés nem kerülhet a fő shortlistbe.

## 3. Belső részek

1. **Job normalizer:** egységes cím, szakma, hely, nyelv, senioritás és forrás.
2. **Hard-gate evaluator:** kizáró és tisztázandó feltételek.
3. **Evidence matcher:** profilbizonyítékot köt minden egyező követelményhez.
4. **Fit scorer:** verziózott képlettel pontoz.
5. **Confidence calculator:** külön méri az adatok megbízhatóságát.
6. **Shortlist service:** csak reális találatot ad, duplikáció nélkül.
7. **ATS analyzer:** a kiválasztott hirdetést veti össze a master CV-vel.
8. **Application Materials Agent:** célzott szövegvázlatot készít.
9. **Document validator/renderer:** tényellenőrzés után PDF/DOCX-előnézetet készít.

## 4. Determinisztikus állásillesztés

### Hard gate

Minden kötelező feltétel állapota: `pass`, `fail` vagy `unknown`.

| Kapu | `fail` hatása | `unknown` hatása |
|---|---|---|
| Kötelező munkavállalási jogosultság | nem ajánlható | tisztázásig nincs fő shortlist |
| Kötelező nyelvi minimum | nem ajánlható | tisztázandó |
| Kötelező képesítés/tanúsítvány | nem ajánlható | tisztázandó |
| Hely/munkamód ütközés | nem ajánlható | tisztázandó |
| Egyértelmű minimumtapasztalat | nem ajánlható, ha bizonyítottan kevés | hiányzó adat bekérése |

### V1 illeszkedési pontszám

Csak hard-gate-en átment hirdetés kap pontot:

| Komponens | Súly |
|---|---:|
| Kötelező és fontos készségek bizonyított lefedettsége | 35 |
| Releváns feladat- és tapasztalategyezés | 25 |
| Senioritás és tapasztalati szint | 15 |
| Iparági/domain egyezés | 10 |
| Nyelvi illeszkedés | 10 |
| Hely, remote és egyéb munkafeltétel | 5 |
| **Összesen** | **100** |

Kezdő szabály:

- `70–100`: fő ajánlás;
- `55–69`: csak „fejlesztéssel elérhető” lista, nem fő ajánlás;
- `0–54`: nem ajánljuk;
- bármely `fail`: nincs fit score, hanem konkrét kizáró ok.

A küszöb és súly csak verziózott, mérési eredménnyel módosítható. Az agent
nem változtathatja meg.

### Confidence

A `fit_score` mellett külön jelenik meg az adatbizonyosság. Ezt a profil
evidence-lefedettsége, a hirdetés parse-minősége és frissessége adja.
Alacsony confidence mellett a rendszer nem állítja biztosan, hogy jó az esély.

## 5. ATS és dokumentumkészítés

Az ATS nem „jósolja meg”, átmegy-e a felhasználó egy munkáltató rendszerén.
Ellenőrzi:

- olvasható szerkezet és szekciók;
- kiválasztott hirdetés kulcsfogalmainak valós lefedettsége;
- kötelező követelmények bizonyítékát;
- dátumok és állítások következetességét;
- gépi feldolgozást zavaró formai elemeket.

Az Application Materials Agent csak megerősített profiltényt használhat.
Hiányzó készséget kétféleképpen kezelhet:

- ha valós, de nincs a CV-ben: javasolhatja a beemelését;
- ha nincs rá bizonyíték: hiányként vagy tanulási célként jelöli, nem írja bele.

Minden generált állításhoz `profile_fact_id` vagy `evidence_id` tartozik.
A validátor blokkolja az árva állítást.

## 6. Adatmodell és API

### Entitások

- `saved_jobs`: owner, job, státusz, megjegyzés.
- `job_match_runs`: profilverzió, szabályverzió, szűrők, időpont.
- `job_matches`: hard gate-ek, komponenspontok, total, confidence, indokok.
- `ats_analyses`: CV-verzió, job-verzió, formai és tartalmi gap.
- `application_packages`: job, profil, státusz, nyelv.
- `application_documents`: típus, vázlatverzió, jóváhagyás, export.
- `document_claim_links`: szövegállítás és profil/evidence kapcsolat.

### API

| Végpont | Feladat |
|---|---|
| `POST /api/v1/jobs/matches` | személyre szabott rangsor futtatása |
| `GET /api/v1/jobs/matches/{run_id}` | shortlist és pontbontás |
| `POST /api/v1/jobs/{id}/save` | állás mentése |
| `POST /api/v1/jobs/{id}/ats` | kiválasztott állás ATS-elemzése |
| `POST /api/v1/applications` | pályázati csomag vázlatának indítása |
| `PATCH /api/v1/applications/{id}/documents/{doc_id}` | felhasználói szerkesztés |
| `POST /api/v1/applications/{id}/approve` | végleges csomag jóváhagyása |
| `GET /api/v1/applications/{id}/export` | PDF/DOCX letöltés |

## 7. Eszközök, jogosultságok és Career GPS

| Eszköz | Típus | Korlát |
|---|---|---|
| `search_jobs` | determinisztikus adat | friss és deduplikált találatok |
| `score_job_fit` | determinisztikus számítás | verziózott képlet |
| `analyze_ats` | determinisztikus elemzés | kiválasztott job + CV |
| `draft_targeted_cv` | agent | igazolt tények |
| `draft_motivation_letter` | agent | igazolt tények + job |
| `validate_document_claims` | determinisztikus guardrail | árva állítás blokkolása |
| `export_application` | renderer | jóváhagyott verzió |

GPS-események: `job_shortlist_created`, `job_selected`,
`ats_analysis_ready`, `application_package_approved`.

## 8. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| Nincs 70+ találat | őszinte eredmény, feltételek lazításának hatása külön |
| Hiányos profil | célzott kérdés, nem általános kulcsszavas rangsor |
| Elavult hirdetés | elavult jelölés vagy kizárás |
| Hirdetésben prompt injection | adatként parse-olva, utasításként tiltva |
| LLM kitalált készséget ír | claim-validator blokkol |
| Duplikált állás | egy kanonikus találat, több forráshivatkozással |
| Agent/API hiba | mentett shortlist megmarad; generálás újraindítható |

Kötelező tesztek: azonos input azonos score, súlyösszeg, hard-gate,
küszöbhatárok, hiányzó adat, junior/senior ütközés, nyelvi blokk,
hallucinált CV-állítás, többfelhasználós izoláció.

## 9. Frontend-megjelenés

- Alapnézetben legfeljebb öt fő ajánlás.
- Kártyán: illeszkedés, confidence, három erősség, legfontosabb hiány,
  forrás és frissesség.
- „Miért ennyi?” alatt látható a teljes komponenspontozás és evidence.
- „Fejlesztéssel elérhető” állások külön, nem keverednek a fő listával.
- ATS csak a kiválasztott állás után jelenik meg.
- CV-módosítás diffnézetben: eredeti, javaslat, indok és bizonyíték.
- A felhasználó mondatonként elfogadhat vagy elutasíthat.

## 10. Mérhető elfogadási feltételek

1. A fő shortlistben nincs hard-gate `fail` vagy tisztázatlan kötelező feltétel.
2. Ugyanaz a profil-, job- és szabályverzió ugyanazt a pontszámot adja.
3. Minden pontkomponens és minden generált szakmai állítás visszakövethető.
4. Igazolatlan készséget a rendszer sem CV-be, sem levélbe nem ír.
5. ATS csak profil/master CV és kiválasztott állás után fut.
6. A top ajánlások relevanciáját kézzel címkézett evalkészleten mérjük;
   indulási kapu: `precision@5 >= 0.80`.
7. PDF- és DOCX-export vizuális és szövegkinyerési regressziós teszten átmegy.
