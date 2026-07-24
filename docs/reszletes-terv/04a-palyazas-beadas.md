# Karrier-Ügynökség — pályázás beadási specifikáció

Állapot: **részletes terv — 2026-07-24**

Kapcsolódó kanonikus dokumentum:
`docs/felhasznaloi-allapotgep.md`

## 1. Cél és hatókör

A pályázási folyamat nem ér véget a CV és motivációs levél elkészítésével.
A rendszer feladata, hogy a jóváhagyott pályázati csomagot a megfelelő
csatornán beadásig vigye, majd a beadást ellenőrizhetően naplózza.

A folyamat határa:

`HIRDETES_ELLENORZOTT → ATS_KESZ → PALYAZATI_CSOMAG_TERVEZET → KULDESRE_JOVAHAGYVA → PALYAZAS_ELINDITVA → PALYAZAS_BEADVA_NAPLOZVA`

Az interjú, elutasítás vagy ajánlat későbbi, felhasználói fiókesemény.

## 2. Alapelvek

1. Egy pályázási munkapéldány pontosan egy álláshirdetéshez tartozik.
2. Több kiválasztott állás több, egymástól elkülönített munkapéldány.
3. Külső műveletet nem az LLM, hanem engedélyezett connector hajt végre.
4. Az agent tervezetet készít; az orchestrator ellenőrzi az állapotot,
   jogosultságot, jóváhagyást és idempotenciát.
5. Küldés előtt a felhasználó a teljes csomagot és célpontot látja.
6. A jóváhagyás egyszer használható, lejár és csak a megjelenített verziókra
   érvényes.
7. CAPTCHA, kétlépcsős azonosítás vagy szolgáltatási tiltás nem kerülhető meg.
8. A „beadva” állapot csak technikai bizonyítékból vagy kifejezett
   felhasználói megerősítésből keletkezhet.

## 3. Jelentkezési csatorna felismerése

A `HIRDETES_ELLENORZOTT` állapot előtt a determinisztikus csatornafelismerő
meghatározza:

| Csatorna | Felismerési bizonyíték | V1 működés |
|---|---|---|
| `email` | ellenőrzött jelentkezési e-mail-cím | tényleges küldés OAuth-kapcsolaton |
| `company_portal` | céges domainhez tartozó jelentkezési URL | oldal megnyitása, vezetett beadás |
| `job_board` | ismert állásportál jelentkezési URL-je | oldal megnyitása, vezetett beadás |
| `external_form` | ellenőrzött külső űrlap URL | oldal megnyitása, vezetett beadás |
| `unknown` | nincs ellenőrzött cím vagy URL | beadás blokkolva, pontosítás |

Az LLM segíthet a hirdetésszöveg értelmezésében, de a cím, domain, URL-séma,
átirányítás, HTTPS és tiltólista ellenőrzése programlogika.

## 4. Pályázati csomag

Minden `application_package` tartalmazza:

- felhasználó és pályázási munkapéldány azonosítója;
- állás és hirdetés rögzített verziója;
- célzott CV jóváhagyandó verziója;
- motivációs levél vagy e-mail-kísérőszöveg verziója;
- szükséges portfóliólink vagy melléklet;
- jelentkezési csatorna;
- címzett vagy céloldal;
- szükséges mezők és dokumentumok listája;
- átadandó személyes adatok listája;
- hiányzó vagy tisztázandó elemek;
- csomag-ujjlenyomat a verziók összekötéséhez.

Küldésre csak teljes és validált csomag jelölhető.

## 5. E-mailes pályázás

### 5.1 Kapcsolat

A felhasználó saját Gmail- vagy Microsoft-fiókját OAuth 2.0-val kapcsolja.
Jelszót az alkalmazás nem kér és nem tárol.

Első támogatott szolgáltatások:

- Gmail API;
- Microsoft Graph `sendMail`.

Csak a küldéshez szükséges legszűkebb jogosultság kérhető. Az access és
refresh token titkosítva, szerveroldalon, felhasználóhoz kötve tárolandó.
A kapcsolat bármikor visszavonható.

### 5.2 Küldési előnézet

Jóváhagyás előtt megjelenik:

- küldő fiók;
- címzett;
- tárgy;
- teljes levéltörzs;
- mellékletek neve, típusa, mérete és dokumentumverziója;
- portfóliólinkek;
- átadott személyes adatok;
- állás és cég;
- jóváhagyás lejárata.

A felhasználó szerkeszthet, visszaléphet vagy jóváhagyhat.
Szerkesztés után új csomag-ujjlenyomat és új jóváhagyás szükséges.

### 5.3 Küldés

1. Backend ellenőrzi a felhasználót.
2. Ellenőrzi a munkapéldány állapotát.
3. Betölti a jóváhagyást és összeveti a csomag-ujjlenyomatot.
4. Idempotenciakulccsal küldési rekordot foglal.
5. Meghívja a Gmail vagy Microsoft connector küldési műveletét.
6. Elmenti a szolgáltató válaszát és üzenetazonosítóját.
7. Auditálja a műveletet személyes tartalom másolása nélkül.
8. A GPS csak sikeres connector-válasz után kap `application_submitted`
   eseményt.

Újrapróbálás ugyanazzal az idempotenciakulccsal nem küldhet második levelet.

### 5.4 Küldési eredmény

- `sent_confirmed`: szolgáltató üzenetazonosítót adott;
- `accepted_unconfirmed`: a szolgáltató átvette, de kézbesítés nem igazolt;
- `failed_retryable`: átmeneti hiba, biztonságosan újrapróbálható;
- `failed_final`: jogosultság, címzett vagy tartalmi hiba;
- `approval_expired`: új előnézet és jóváhagyás kell;
- `connection_required`: a levelezőfiókot újra kell kapcsolni.

A rendszer nem állíthatja, hogy a munkáltató megkapta vagy elolvasta a levelet,
ha erre nincs szolgáltatói bizonyíték.

## 6. Karrieroldalas és állásportálos beadás

### 6.1 Technikai határ

A webalkalmazás önmagában nem tölthet ki tetszőleges külső weboldalt a
böngésző biztonsági korlátai miatt. A teljes automatizáláshoz később
engedélyezett Chrome-bővítmény vagy ellenőrzött böngészőautomatizálási
környezet szükséges.

### 6.2 V1 — teljes, vezetett beadás

A V1 nem áll meg egy link megjelenítésénél:

1. ellenőrzi és megnyitja a jelentkezési URL-t;
2. egy oldalsó beadási panelen megjeleníti a szükséges adatokat;
3. biztosítja a célzott CV és levél letöltését;
4. mezőnként másolható válaszokat ad;
5. ellenőrzőlistán követi a kitöltést és feltöltést;
6. a felhasználó a külső oldalon végzi el a végső beadást;
7. visszatéréskor megjelöli: `beadtam` vagy `nem sikerült`;
8. bizonyítékként opcionálisan visszaigazoló azonosítót vagy képernyőképet ad;
9. a rendszer naplózza az eseményt és a forrását.

Ez használható, befejezett folyamat, de nem állít hamis automatikus beadást.

### 6.3 V2 — Chrome-bővítményes kitöltés

A bővítmény:

- csak aktív felhasználói indításra fut;
- csak az aktuális, jóváhagyott céloldalon kap ideiglenes hozzáférést;
- felismeri a mezőket és a backendtől strukturált mezőértékeket kér;
- kitölti az engedélyezett szöveges mezőket;
- feltölti a jóváhagyott dokumentumverziókat;
- ismeretlen vagy érzékeny kérdésnél megáll;
- CAPTCHA-nál, 2FA-nál és végső beadásnál átadja a vezérlést;
- beadási bizonyítékot csak a felhasználó jóváhagyásával küld vissza.

Jelszó, CAPTCHA-válasz, egészségügyi adat, védett tulajdonság vagy jogi
nyilatkozat nem tölthető ki önálló agentdöntésből.

## 7. Jóváhagyási szerződés

Az `ApprovalRequest` kötelező mezői:

| Mező | Tartalom |
|---|---|
| `user_id` | tulajdonos |
| `application_id` | pályázási munkapéldány |
| `action_type` | `send_email`, `open_portal`, később `fill_portal` |
| `target` | normalizált e-mail vagy HTTPS URL |
| `package_fingerprint` | a jóváhagyott csomag ujjlenyomata |
| `document_versions` | pontos CV/levél/portfólió verziók |
| `personal_data_fields` | átadandó személyes adatok |
| `expires_at` | lejárat |
| `status` | pending/approved/rejected/expired/consumed |
| `approved_at` | jóváhagyás ideje |
| `consumed_at` | végrehajtás ideje |

Egy jóváhagyás csak egyszer és csak változatlan célra, tartalomra és
dokumentumverzióra használható.

## 8. Adatmodell

Új vagy kiegészítendő entitások:

- `applications`: állás, felhasználó, állapot, csatorna;
- `application_packages`: profil-, hirdetés- és csomagverzió;
- `application_documents`: dokumentumtípus és jóváhagyott fájlverzió;
- `application_targets`: e-mail/URL, domain és ellenőrzési eredmény;
- `email_connections`: szolgáltató, titkosított OAuth-tokenhivatkozás, scope;
- `submission_attempts`: idempotenciakulcs, állapot, szolgáltatóazonosító;
- `submission_evidence`: technikai vagy felhasználói beadási bizonyíték;
- `approval_requests`: pontos jóváhagyási szerződés;
- `audit_events`: művelet, eredmény és hivatkozások;
- `active_tasks`: megszakítható és folytatható beadási feladat.

Nyers OAuth-token, teljes CV vagy levéltartalom nem kerül auditnaplóba.

## 9. API-terv

| Végpont | Feladat |
|---|---|
| `POST /api/v1/applications` | pályázási munkapéldány létrehozása |
| `GET /api/v1/applications/{id}` | állapot és csomag lekérése |
| `POST /api/v1/applications/{id}/channel/resolve` | jelentkezési csatorna ellenőrzése |
| `POST /api/v1/applications/{id}/package` | csomagtervezet készítése |
| `POST /api/v1/applications/{id}/validate` | dokumentum- és célvalidáció |
| `POST /api/v1/applications/{id}/approval-preview` | pontos előnézet |
| `POST /api/v1/applications/{id}/approve` | egyszeri jóváhagyás |
| `POST /api/v1/applications/{id}/submit/email` | e-mail küldése |
| `POST /api/v1/applications/{id}/submit/portal` | vezetett beadás indítása |
| `POST /api/v1/applications/{id}/submission-evidence` | beadás igazolása |
| `POST /api/v1/integrations/email/{provider}/connect` | OAuth kapcsolat indítása |
| `DELETE /api/v1/integrations/email/{provider}` | kapcsolat visszavonása |

Minden író végpont JWT-t, tulajdonosi ellenőrzést, bemeneti sémát és rate
limitet használ. Küldési végpont idempotenciakulcs nélkül nem hívható.

## 10. Flow, agent és orchestrator

### Flow

- elmagyarázza az aktuális lépést;
- bekéri a hiányzó, felhasználó által eldöntendő adatot;
- megjeleníti a beadási előnézetet;
- javítási vagy jóváhagyási döntést kér;
- közérthetően ismerteti a küldési eredményt.

### Application Materials Agent

- célzott CV- és levéltervezetet készít igazolt tényekből;
- e-mail tárgyat és kísérőszöveget javasol;
- strukturált mezőválasz-tervezetet készíthet;
- nem küld, nem kattint és nem módosít állapotot.

### Determinisztikus orchestrator

- ellenőrzi az állapotátmenetet;
- ellenőrzi a csomag teljességét és ujjlenyomatát;
- létrehozza és elfogyasztja a jóváhagyást;
- kezeli az idempotenciát, timeoutot és újrapróbálást;
- meghívja az engedélyezett connectort;
- naplóz és GPS-eseményt bocsát ki.

## 11. Frontend

A Flow beszélgetésében megjelenő pályázási munkakártya:

1. állás és cég;
2. beadási csatorna;
3. csomag készültsége;
4. CV, levél és portfólió előnézete;
5. hiányzó adatok;
6. átadandó személyes adatok;
7. `Javítom`, `Jóváhagyom és elküldöm` vagy `Megnyitom a jelentkezést`;
8. valós folyamatállapot;
9. beadási visszaigazolás és auditazonosító.

Hamis százalékos animáció vagy automatikus továbbhaladás nem jelenhet meg.

## 12. Hibakezelés

| Hiba | Viselkedés |
|---|---|
| hiányzó/hibás címzett | küldés blokkolva |
| lejárt OAuth-token | újrakapcsolás, csomag megmarad |
| szolgáltatói timeout | állapot lekérdezése, nem vak újraküldés |
| duplikált kérés | korábbi küldési eredmény visszaadása |
| melléklet túl nagy/hibás | validációs hiba, nincs küldés |
| lejárt jóváhagyás | új előnézet szükséges |
| csomag módosult | régi jóváhagyás érvénytelen |
| portál CAPTCHA/2FA | átadás a felhasználónak |
| portál szerkezete megváltozott | automatikus kitöltés leáll, vezetett mód |
| külső oldal prompt injection | webtartalom adatként kezelve |

## 13. Kötelező tesztek

- más felhasználó pályázásához nincs hozzáférés;
- jóváhagyás nélkül nincs küldés;
- módosított csomaggal a régi jóváhagyás használhatatlan;
- ugyanaz az idempotenciakulcs nem küld kétszer;
- hibás címzett/domain blokkolódik;
- igazolatlan dokumentumverzió nem csatolható;
- lejárt OAuth-token biztonságosan kezelődik;
- szolgáltatói timeout nem okoz duplikált küldést;
- CAPTCHA/2FA nem kerül megkerülésre;
- beadási esemény csak bizonyítékból keletkezik;
- auditnapló nem tartalmaz nyers tokent vagy teljes személyes dokumentumot.

## 14. Megvalósítási sorrend

### A. Teljes e-mailes vertikális szelet

1. adatmodell és RLS;
2. Gmail OAuth-kapcsolat;
3. csomagvalidáció és jóváhagyási előnézet;
4. idempotens Gmail-küldés mellékletekkel;
5. visszaigazolás, audit és Career GPS;
6. frontend munkakártya;
7. automatizált tesztek.

Ez már végponttól végpontig befejezett, valódi pályázás.

### B. Microsoft e-mail

Ugyanaz a connector-szerződés Microsoft Graph implementációval.

### C. Vezetett karrieroldalas beadás

URL-ellenőrzés, oldalsó beadási panel, dokumentumok, ellenőrzőlista és
felhasználói beadási bizonyíték.

### D. Chrome-bővítményes támogatás

Csak az A–C szakasz biztonsági és használhatósági tesztjei után.

## 15. Elfogadási feltételek

1. Egy tesztfelhasználó Gmail-fiókot OAuth-val csatlakoztat.
2. Egy konkrét álláshoz teljes pályázati csomag készül.
3. A felhasználó pontos előnézetet lát.
4. Jóváhagyás nélkül semmilyen e-mail nem küldhető.
5. Jóváhagyás után a levél egyszer, a jóváhagyott mellékletekkel elküldhető.
6. A szolgáltatóazonosító, audit és GPS-esemény létrejön.
7. Hiba esetén a csomag nem vész el és nem történik duplikált küldés.
8. Karrieroldalas jelentkezésnél a vezetett folyamat beadásig és naplózásig
   eljut, akkor is, ha az utolsó kattintást a felhasználó végzi.


