# 1. Platform, adat és biztonság

## 1. Cél és hatókör

Ez a főrész ad közös, biztonságos futási alapot minden funkciónak. Ide tartozik
a hitelesítés, adatelérés, fájlkezelés, jogosultság, háttérfeladat, agentfutás,
jóváhagyás, naplózás és költségvédelem.

Nem tartozik ide állásrangsor, karriertanács vagy dokumentumírás: ezeket a
többi főrész végzi a platform szabályai között.

## 2. Bemenet és adatforrás

| Bemenet | Forrás | Kezelés |
|---|---|---|
| Supabase JWT | böngésző cookie | aláírás-, issuer-, audience-, expiry- és subject-ellenőrzés |
| API-kérés | Next.js | séma, méret, jogosultság, rate limit és idempotencia |
| CV/projektfájl | felhasználó | típus-, méret-, tartalom- és kártevőkapu |
| Katalógusimport | Jooble, EURES és ellenőrzött forrás | forrásazonosító, dátum, duplikáció és adatminőség |
| Agentkérés | orchestrator | engedélyezett séma, tool-lista és futási keret |
| Konfiguráció | szerverkörnyezet | titokkezelés, verziózott szabályok és tiltott kliensoldali kitettség |

## 3. Belső részek

1. **Auth gateway:** minden védett FastAPI-végpont előtt hitelesít.
2. **Policy layer:** erőforrás- és műveletszintű jogosultságot ellenőriz.
3. **Supabase data layer:** típusos repository-kon keresztül olvas és ír.
4. **Ingestion pipeline:** külső adatot normalizál, duplikál, frissességet mér.
5. **Storage quarantine:** feltöltést ellenőrzésig nem tesz feldolgozhatóvá.
6. **Job runner:** tartós állapotú háttérfeladatot futtat, újrapróbálási limittel.
7. **Approval service:** érzékeny műveletet megállít és egyszeri döntést kér.
8. **Agent runtime:** strukturált bemenetet, toolsémát és futási limitet biztosít.
9. **Audit/telemetria:** technikai eseményt, hibát, költséget és szabályverziót rögzít.

Next.js SSR-ben a szerveroldali oldalvédelem validált claimre épül; a
cookie-ból visszaadott, újra nem ellenőrzött session önmagában nem
jogosultsági bizonyíték. A rögzített célfuttatókörnyezet Node.js 24.x.

## Megvalósítási állapot — első biztonsági szelet

| Elem | Állapot |
|---|---|
| Pontos runtime- és SDK-verziók | elkészült |
| Publishable/secret környezeti szerződés | elkészült |
| Supabase SSR belépés és munkamenetfrissítés | elkészült |
| FastAPI JWT-kapu minden üzleti végponton | elkészült |
| Kérésméret, PDF magic byte, alap rate limit és biztonsági headerek | elkészült |
| Explicit `api`, nem exponált `private` séma és működési táblák | migráció elkészült, élesben még nincs alkalmazva |
| `tudas_kereses` search path és pgvector-séma javítása | migráció elkészült, élesben még nincs alkalmazva |
| Függőségi audit, titokscan, backendteszt és frontend-build CI | elkészült |
| Elosztott rate limit, karantén/kártevővizsgálat | következő biztonsági szelet |
| Job/approval/audit szolgáltatás és API | következő biztonsági szelet |
| Kétfelhasználós RLS-integrációs teszt | migráció alkalmazása után |
| Kiszivárgott jelszó elleni Auth-kapcsoló | Supabase Dashboardban bekapcsolandó |

## 4. Determinisztikus logika és agenthatár

Minden hitelesítési, jogosultsági, fájl-, URL-, adatminőségi, rate-limit,
jóváhagyási és naplózási döntés determinisztikus.

Agent:

- nem olvashat tetszőleges táblát vagy fájlt;
- nem építhet SQL-t;
- nem kaphat secret/service kulcsot;
- nem módosíthat jogosultságot;
- nem hajthat végre külső vagy tartós írást közvetlenül.

Az agent csak névvel és sémával rendelkező backend-toolon keresztül kérhet
adatot. A tool újra ellenőrzi a felhasználót, a hatókört és a limitet.

## 5. Adatmodell és API

### Adatterületek

| Terület | Javasolt hely | Hozzáférés |
|---|---|---|
| Nyilvános szakmai katalógus | explicit módon exponált API-séma | olvasás, szükség szerint anon/authenticated |
| Saját profil és dokumentum | RLS-védett felhasználói táblák | csak tulajdonos |
| Agent-, job- és auditadat | nem exponált belső séma | kizárólag backend |
| Fájltartalom | privát Storage bucket | rövid életű signed URL vagy backend-stream |
| Publikus portfólió | elkülönített publikációs tárhely | csak jóváhagyott verzió |

### Közös működési entitások

- `background_jobs`: típus, owner, állapot, próbálkozás, timeout, eredményhivatkozás.
- `approval_requests`: owner, művelet, előnézet-hash, állapot, lejárat, döntési idő.
- `agent_runs`: agent, trace-id, szabály- és promptverzió, státusz, token/költség.
- `audit_events`: szereplő, esemény, erőforrás, eredmény, request-id.
- `data_import_runs`: forrás, időablak, beolvasott/elutasított/duplikált rekordok.

### Platform-végpontok

| Végpont | Feladat |
|---|---|
| `GET /api/v1/me` | hitelesített felhasználó minimális adata |
| `POST /api/v1/uploads` | feltöltési folyamat indítása |
| `GET /api/v1/jobs/{id}` | saját háttérfeladat állapota |
| `POST /api/v1/approvals/{id}/decision` | pontos művelet jóváhagyása vagy elutasítása |
| `DELETE /api/v1/me/data` | export/előnézet után felhasználói adatok törlése |
| `GET /health/live` | folyamat él-e |
| `GET /health/ready` | adatbázis és kötelező szolgáltatások elérhetők-e |

Minden író végpont fogad `Idempotency-Key` fejlécet. Ugyanaz a kulcs és
felhasználó nem indíthatja el kétszer ugyanazt a műveletet.

## 6. Eszközök, jogosultságok és jóváhagyások

| Művelet | Automatikus | Jóváhagyás |
|---|---|---|
| Saját profil olvasása | igen | nem |
| Saját vázlat mentése | igen | nem |
| Profil tényének megerősítése | nem | felhasználói megerősítés |
| Dokumentum generálása | igen, vázlatként | nem |
| Dokumentum véglegesítése/letöltése | nem | előnézet után |
| Külső elküldés vagy publikálás | nem | mindig |
| Fiókadat törlése | nem | újrahitelesítés és megerősítés |
| Admin import | nem | adminjog és audit |

## 7. Kimenet és Career GPS

A platform nem ad karriertanácsot. A többi főrésznek a következő biztos
kimeneteket adja:

- `AuthenticatedContext`;
- `AuthorizedResource`;
- `ValidatedUpload`;
- `TrustedCatalogRecord`;
- `ApprovalState`;
- `JobState`;
- `PolicyDecision`.

Career GPS csak sikeres, auditált domain-eseményt kap. Sikertelen vagy
félbehagyott háttérfeladat nem növelheti a készültséget.

## 8. Hibakezelés és biztonsági tesztek

| Kockázat | Kötelező védelem | Teszt |
|---|---|---|
| Másik felhasználó rekordja | owner-alapú RLS és backend policy | kétfelhasználós BOLA/IDOR teszt |
| Hamis vagy lejárt JWT | claim- és aláírás-ellenőrzés | lejárt, hibás audience, módosított token |
| Secret kliensoldalon | build- és repository-scan | tiltott env név buildhibát okoz |
| Rosszindulatú feltöltés | karantén, MIME/magic byte, méretlimit | dupla kiterjesztés, polyglot, túlméret |
| Prompt injection | strukturált kivonat és tool-allowlist | CV/web/RAG támadási korpusz |
| Ismételt költséges kérés | felhasználó/IP kvóta, cache, timeout | párhuzamos és replay terhelés |
| Jóváhagyás újrafelhasználása | művelet-hash, owner, lejárat, egyszeriség | módosított és replayelt jóváhagyás |
| Naplózott személyes adat | redakció és mező-allowlist | log snapshot PII-kereséssel |

### Meglévő Supabase-kockázatok lezárási kapuja

A megvalósítás első migrációs csomagja addig nem tekinthető késznek, amíg:

- minden exponált táblához tényleges RLS-policy tartozik;
- az exponált view `security_invoker` elvű, vagy nincs kliensszerepeknek megadva;
- `tudas_kereses` rögzített, biztonságos `search_path`-ot használ;
- a vektorbővítmény és belső objektumok nem adnak szükségtelen publikus felületet;
- a kiszivárgott jelszavak elleni Auth-védelem be van kapcsolva;
- az adat- és biztonsági advisor nem jelez megoldatlan kritikus hibát.

## 9. Frontend-megjelenés

- Authállapot és lejárt munkamenet érthető, adatvesztés nélküli üzenetet kap.
- Feltöltésnél külön látszik: feltöltés, ellenőrzés, feldolgozás, kész/hiba.
- Jóváhagyási panel megmutatja a **pontos** műveletet és érintett adatot.
- Háttérfeladat megszakítható, újrapróbálható és nem blokkolja az egész oldalt.
- Biztonsági hiba nem tár fel táblanevet, SQL-t, tokent vagy belső trace-t.

## 10. Mérhető elfogadási feltételek

1. Védett API érvényes JWT nélkül mindig 401; idegen rekordhoz mindig 403/404.
2. RLS integrációs teszt minden felhasználói táblára két külön userrel fut.
3. Egyetlen kliensbundle és log sem tartalmaz secret/service kulcsot vagy nyers CV-t.
4. Minden agenttool és író API séma-validált, idő- és méretlimites.
5. A jóváhagyás nélküli küldés, publikálás és törlés technikailag lehetetlen.
6. A háttérfeladat újraindítás után folytatható vagy szabályosan lezárható.
7. Biztonsági, adatbázis- és függőségi ellenőrzés CI-ben kötelező.
