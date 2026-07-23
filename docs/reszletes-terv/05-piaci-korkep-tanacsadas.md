# 5. Piaci körkép és karriertanácsadás

## 1. Cél és hatókör

Ez a főrész két összekapcsolt, de elkülönített eredményt ad:

1. **Piaci körkép:** a felhasználó szakmájának tényszerű, vizuális helyzete.
2. **Karriertanácsadás:** a profil, a teszteredmények, a piac és az ellenőrzött
   tudásanyag alapján értelmezett következő lépések.

A grafikonokat és mérőszámokat program számolja. Nincs külön „piaci elemző
agent”. A Career Advisor kizárólag a már kiszámolt adatot értelmezi.

## 2. Bemenet és adatforrás

| Adat | Elsődleges forrás | Kötelező metaadat |
|---|---|---|
| Hirdetésszám és trend | `hirdetesek`, `piaci_statisztikak` | forrásdátum, szakmakód, minta |
| Készségigény | `hirdetes_keszseg`, `keszsegek` | előfordulás, időszak, normalizálás |
| Cég- és területi kép | `cegek`, hirdetések | rekordforrás és időszak |
| Szakmaleírás | `szakmak`, `feor_lista` | verzió/forrás |
| Tudásanyag | `tudasanyag` + vektoros keresés | dokumentum, szakasz, dátum |
| Tesztválasz | felhasználó | teszt- és értékelőkulcs-verzió |
| Személyes kontextus | megerősített profil | profilverzió |

Ha egy mutatóhoz nincs megfelelő adatmező — például nincs megbízható
béradat — a rendszer nem rajzol ki és nem becsül ki ilyen grafikont.

## 3. Belső részek

1. **Data quality gate:** frissesség, duplikáció, hiány és minimum mintanagyság.
2. **Market query service:** szakma, időszak és régió szerinti aggregáció.
3. **Chart data builder:** frontendfüggetlen idősor és kategóriaadat.
4. **Market snapshot:** a felhasznált adatok változatlan, dátumozott képe.
5. **Test engine:** verziózott kérdőív és determinisztikus értékelés.
6. **RAG retriever:** engedélyezett tudásanyagrészleteket keres.
7. **Career Advisor:** a négy forrásból tanácsot fogalmaz, hivatkozásokkal.
8. **Advice validator:** tiltja a forrás nélküli piaci tényt és diagnózist.

## 4. Determinisztikus logika és agenthatár

### Piaci számítás

Program számolja többek között:

- aktív és új hirdetések száma;
- valódi forrásdátum szerinti trend;
- leggyakoribb és gyorsan változó készségek;
- területi, munkamód- és senioritásmegoszlás, ha az adat elég teljes;
- legaktívabb cégek;
- minta, adatfrissesség és lefedettség.

A `collected_at` nem helyettesítheti a hirdetés vagy forrás valódi dátumát.
Ismeretlen dátumú rekord trendbe nem kerül.

### Tesztértékelés

- kérdés, válaszskála és pontozókulcs verziózott;
- visszafelé kódolt itemeket program kezeli;
- hiányos kitöltésnél nincs végső eredmény;
- eredményhez skálák és közérthető korlátok tartoznak;
- a teszt támogatja a döntést, de nem választ szakmát a felhasználó helyett.

### Career Advisor

Az Advisor a következő strukturált kimenetet adja:

```text
CareerAdvice
  summary
  strengths[]: profile evidence hivatkozással
  risks[]: profile/market/test hivatkozással
  recommendations[]: lépés, indok, források, prioritás
  uncertainties[]
  follow_up_question
```

Az Advisor nem keres szabadon weben alapértelmezetten. Ha a helyi adat nem
elég egy kifejezetten friss kérdéshez, csak olvasó, forrás-allowlistes keresés
indítható; a találat adatként, forrásdátummal kerül a rendszerbe.

## 5. Adatmodell és API

### Entitások

- `market_snapshots`: szakma, időszak, régió, források, minőség.
- `market_metrics`: snapshot, metric key, value, minta, dimenzió.
- `market_chart_series`: grafikonhoz kész, verziózott sorok.
- `assessment_definitions`: kérdések, skálák, értékelőkulcs, verzió.
- `assessment_runs`: owner, definíció, állapot, befejezés.
- `assessment_answers`: run, kérdés, validált válasz.
- `assessment_results`: skálák, összesítés, korlátok.
- `advice_sessions`: profil-, market-, test- és tudásanyag-hivatkozások.
- `advice_recommendations`: javaslat, prioritás, források, user döntés.

### API

| Végpont | Feladat |
|---|---|
| `GET /api/v1/market/overview` | szakmához tartozó aktuális snapshot |
| `GET /api/v1/market/trends` | idősort és adatminőséget ad |
| `GET /api/v1/market/skills` | keresett készségek és változás |
| `GET /api/v1/assessments` | elérhető tesztek és céljuk |
| `POST /api/v1/assessments/{id}/runs` | kitöltés indítása |
| `PUT /api/v1/assessments/runs/{id}/answers` | válasz mentése |
| `POST /api/v1/assessments/runs/{id}/complete` | determinisztikus értékelés |
| `POST /api/v1/advice` | forrásolt tanácsadói összegzés |

## 6. Eszközök, jogosultságok és jóváhagyások

| Eszköz | Használó | Korlát |
|---|---|---|
| `get_market_snapshot` | Flow/Advisor | aggregált adat |
| `get_profile_for_advice` | Advisor | minimális szükséges mezők |
| `get_assessment_result` | Advisor | saját, befejezett teszt |
| `search_knowledge_base` | Advisor | top-k, jogosult corpus, forrással |
| `search_verified_web` | Advisor, kivételesen | read-only, allowlist, idő- és találatlimit |
| `save_advice_decision` | backend | felhasználói döntés után |

Tanács előállítása nem igényel jóváhagyást. Profil, cél vagy GPS módosítása
viszont csak a felhasználó által elfogadott javaslatból történhet.

## 7. Kimenet és Career GPS módosítása

Kimenetek:

- interaktív, dátumozott piaci dashboard;
- készségtrend és saját profil-gap;
- determinisztikus teszteredmény;
- hivatkozott, prioritásos tanács;
- bizonytalanság és következő döntés.

GPS-események: `market_snapshot_ready`, `assessment_completed`,
`advice_reviewed`, `recommendation_accepted`.

Az Advisor szövege nem módosítja automatikusan a felhasználó célját.

## 8. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| Kevés minta | szám helyett figyelmeztetés vagy tágabb kategória |
| Elavult adat | dátum és elavultság látható; nincs aktuális állítás |
| Hiányzó forrásdátum | trendből kizárás |
| RAG nem talál bizonyítékot | „nincs elég adat”, nem saját tudásból pótlás |
| RAG prompt injection | részlet adatként kezelve, toolt nem vezérel |
| Félbehagyott teszt | vázlat mentése, eredmény nélkül |
| Kimerültségre utaló válasz | támogató nyelv, de nincs klinikai diagnózis |

Kötelező tesztek: aggregáció SQL-aranymintával, dátumzónák, duplikáció,
minimum minta, tesztkulcs, RAG-citáció, forrás nélküli agentállítás és
prompt-injection korpusz.

## 9. Frontend-megjelenés

### Piaci körkép

A másik alkalmazásban már működő vizualizációs logika modern Next.js
komponensekben jelenik meg:

- kereslet idősora;
- top készségek és saját készségjelölés;
- területi/munkamód megoszlás;
- aktív cégek;
- adatfrissesség és mintanagyság.

Grafikonra kattintva Flow rövid, az adott adathoz kötött magyarázatot ad.
Nem kell külön „piaci agenttel” beszélgetni.

### Tanácsadás

- profil, teszt, piac és tudásanyag külön forráskártyán látszik;
- javaslatonként „miért?”, bizonyíték és következő lépés;
- a felhasználó elfogadhatja, elutasíthatja vagy későbbre teheti.

## 10. Mérhető elfogadási feltételek

1. Minden grafikonérték reprodukálható SQL/függvény eredményből.
2. Minden piaci kijelentéshez forrásdátum, időszak és mintanagyság tartozik.
3. Hiányzó adatból nem készül becsült tény vagy félrevezető grafikon.
4. A teszt azonos válasz- és kulcsverzióra azonos eredményt ad.
5. Advisor-ajánlás minden tényállítása létező profil-, market-, test- vagy
   tudásanyag-hivatkozást tartalmaz.
6. Prompt injection nem változtat toolhívást vagy forrást.
7. A piaci dashboard reszponzív és vizuális regressziós teszttel védett.
