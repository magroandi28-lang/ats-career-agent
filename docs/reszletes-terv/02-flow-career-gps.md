# 2. Flow és Career GPS

> **Kanonikus elsőbbség:** a felhasználói utaknál, állapotátmeneteknél és
> jóváhagyási pontoknál a
> [felhasználói állapotgép](../felhasznaloi-allapotgep.md) az irányadó.

## 1. Cél és hatókör

Flow az alkalmazás egyetlen látható beszélgetőtársa. Megérti a felhasználó
célját, megállapítja a hiányzó adatot, egyetlen következő lépést ajánl, majd
a megfelelő szolgáltatást vagy specialistát indítja.

A Career GPS a jobb oldalon tényszerűen mutatja, hogyan épül a karrierút:
mi igazolt, mi hiányzik, mi készül, mi a következő döntés.

Flow nem pontoz, nem rangsorol, nem módosít profilt és nem engedélyez saját
magának műveletet.

## 2. Bemenet és adatforrás

| Bemenet | Forrás | Bizalmi szint |
|---|---|---|
| Aktuális üzenet | felhasználó | nem megbízható szöveg |
| Beszélgetési állapot | saját session | ellenőrzött, verziózott |
| Profilösszefoglaló | profil service | ellenőrzött mezők és hiányok |
| Career GPS | GPS service | hiteles állapot |
| Aktív munkakártya | orchestrator | hiteles futási állapot |
| Specialistakimenet | strukturált agentoutput | séma után használható |
| Szolgáltatáskimenet | determinisztikus backend | hiteles, szabályverzióval |

## 3. Belső részek

1. **Intent classifier:** engedélyezett szándék-enumot ad.
2. **Context builder:** csak a szükséges profil- és állapotrészletet állítja össze.
3. **Policy router:** megmondja, mely művelet engedélyezett az aktuális állapotban.
4. **Flow Manager:** közérthetően kérdez vagy összefoglal.
5. **Tool dispatcher:** egyetlen engedélyezett műveletet indít.
6. **Response composer:** strukturált agentkimenetből UI-választ készít.
7. **GPS projector:** domain-eseményekből újraépíti a jobb oldali állapotot.

## 4. Determinisztikus logika és agenthatár

### Determinisztikus

- engedélyezett intentek és műveletek;
- kötelező adatmezők;
- állapotátmenetek;
- tooljogosultság és jóváhagyási igény;
- GPS-készültség és blokkolók;
- hibakezelés és fallback;
- a frontendnek küldött eseménytípusok.

### Flow Manager

Flow csak a következő strukturált szerződést adhatja:

```text
FlowDecision
  intent: engedélyezett enum
  response_message: rövid szöveg
  proposed_action: engedélyezett action vagy null
  required_fields: ismert mezők listája
  specialist_request: engedélyezett specialista vagy null
  evidence_refs: létező hivatkozások
  confidence: 0..1
```

Ha a séma hibás, a művelet nem fut le. A jelenlegi szabad szöveges
`[FLOW_AKCIO: ...]` jelölések és regex-alapú vezérlés megszűnnek.

Alacsony bizonyosságnál Flow rövid pontosító kérdést tesz fel, nem találgat.

## 5. Állapotmodell, adatmodell és API

### GPS-területek

| Terület | Példaállapot |
|---|---|
| Profil | nincs → vázlat → ellenőrzendő → megerősített |
| Karriercél | nyitott → kiválasztott → validált |
| Piaci kép | nincs → betöltve → elavult |
| Felkészültség | hiányok → terv → folyamatban → megfelelő |
| Pályázás | nincs shortlist → shortlist → anyag kész → beadás követése |
| Portfólió | nincs → tartalom készül → előnézet → publikált |
| Speciális út | pályaváltás, képzés vagy külföld aktív/inaktív |

Nem egyetlen mesterséges százalék készül. Minden terület saját, magyarázható
állapotot kap.

### Domain-események

- `profile_draft_created`
- `profile_fact_confirmed`
- `career_goal_selected`
- `market_snapshot_ready`
- `job_shortlist_created`
- `application_package_approved`
- `transition_path_selected`
- `training_selected`
- `foreign_shortlist_created`
- `portfolio_preview_ready`
- `portfolio_published`

Agent nem írhat eseményt. A backend a sikeres műveletből állítja elő.

### Tárolás

- `flow_sessions`: owner, állapot, aktív cél és utolsó aktivitás.
- `flow_messages`: role, redaktált tartalom, strukturált hivatkozások.
- `career_gps_events`: eseménytípus, payload, szabályverzió, actor.
- `career_gps_snapshots`: a gyors megjelenítéshez újraépíthető nézet.
- `active_tasks`: futó, jóváhagyásra váró vagy hibás feladat.

### API

| Végpont | Feladat |
|---|---|
| `POST /api/v1/flow/messages` | üzenet feldolgozása és futás indítása |
| `GET /api/v1/flow/stream/{run_id}` | tipizált SSE-események |
| `POST /api/v1/flow/runs/{id}/cancel` | saját futás megszakítása |
| `GET /api/v1/career-gps` | aktuális projekció |
| `GET /api/v1/career-gps/events` | saját, felhasználói nyelvű előzmény |
| `POST /api/v1/career-gps/next-action` | determinisztikus következő lehetőségek |

## 6. Eszközök, jogosultságok és jóváhagyások

| Flow-eszköz | Típus | Írás |
|---|---|---|
| `get_profile_summary` | adat | nincs |
| `get_career_gps` | adat | nincs |
| `get_market_summary` | adat | nincs |
| `find_matching_jobs` | determinisztikus művelet | eredménycache |
| `ask_career_advisor` | agent mint tool | nincs |
| `draft_application_material` | agent mint tool | vázlat |
| `design_portfolio` | agent mint tool | vázlat |
| `propose_profile_update` | javaslat | csak felhasználói megerősítéssel |
| `request_external_action` | jóváhagyási kérés | végrehajtás csak külön döntéssel |

Flow nem kap általános web-, SQL-, e-mail- vagy publikálási eszközt.

## 7. Kimenet és Career GPS módosítása

A frontend mindig tipizált eseményt kap:

- `message_delta`
- `status_changed`
- `question_required`
- `card_ready`
- `approval_required`
- `gps_updated`
- `completed`
- `failed`

Flow szövege önmagában nem módosít GPS-t. A `gps_updated` csak sikeres
domain-esemény után érkezhet.

## 8. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| Ismeretlen kérés | egy rövid pontosító kérdés |
| Hiányzó kötelező profiladat | célzott adatbekérés, nem üres objektum továbbítása |
| Hibás agent-JSON | egyszeri javítási kísérlet, majd biztonságos fallback |
| Tool timeout | megszakítás, részállapot megőrzése, újrapróbálás |
| Prompt injection | utasításként figyelmen kívül, adatként feldolgozható |
| Tiltott művelet kérése | elutasítás és engedélyezett alternatíva |
| Kettős kattintás/replay | azonos futás, nincs duplikált művelet |
| Lejárt jóváhagyás | új előnézet és új döntés szükséges |

Kötelező evalok: intentpontosság, helyes toolválasztás, hiányzó adat
felismerése, hallucinált profilállítás, prompt injection, túl sok toolhívás és
rossz állapotátmenet.

## 9. Frontend-megjelenés

### Asztali

- Bal, nagyobb terület: Flow, aktuális kérdés és munkakártya.
- Jobb, rögzített panel: GPS-területek, blokkolók, bizonyítékok és következő lépés.
- Egyszerre egy elsődleges gomb; további lehetőségek másodlagosak.
- A GPS változása rövid animációval látható, de csak valós esemény után.

### Mobil

- Flow teljes szélességen.
- A GPS alsó, felhúzható panel.
- Jóváhagyás teljes képernyős, pontos előnézettel.

### Induló állapot

Flow három értelmes belépési lehetőséget kínál:

1. „Van CV-m, nézzük meg.”
2. „Nincs CV-m, építsük fel a profilomat.”
3. „Pályát vagy országot váltanék.”

Nem kell a felhasználónak előre megértenie a funkciók menüjét.

## 10. Mérhető elfogadási feltételek

1. Szabad szöveges action-tag vagy regex nem vezérelhet funkciót.
2. Minden toolhívás érvényes `FlowDecision` és policy-engedély után történik.
3. Flow üres profilból nem indít személyre szabott rangsort vagy dokumentumot.
4. GPS száz százalékban újraépíthető az eseménynaplóból.
5. Agenthiba nem ír adatot és nem változtat GPS-állapotot.
6. A négy fő felhasználói út Playwright E2E-teszttel végigjárható.
7. Mobil és asztali nézetben a felhasználó mindig látja az aktuális következő lépést.
