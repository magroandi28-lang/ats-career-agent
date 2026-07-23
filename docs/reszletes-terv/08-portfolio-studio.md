# 8. Portfólió Stúdió

## 1. Cél és hatókör

A Portfólió Stúdió professzionális, dinamikus HTML-portfóliót készít
tetszőleges szakmai projektekből. Nem néhány előre rögzített eszközre épül:
GitHub, n8n, dashboard, kutatás, tesztautomatizálás, design, publikáció,
videó, dokumentum vagy későbbi új eszköz egyaránt bemutatható.

A Portfolio Designer megtervezi a vizuális és tartalmi szerkezetet. A
biztonságos HTML-t determinisztikus renderelő állítja elő.

## 2. Bemenet és adatforrás

| Bemenet | Forrás |
|---|---|
| Szakmai profil és cél | megerősített profil |
| Projektadat | felhasználói bevitel, igazolt profile project |
| Link | GitHub, élő demo, n8n vagy bármely https forrás |
| Fájl és kép | privát Storage, ellenőrzött feltöltés |
| Eredmény/hatás | felhasználói tény evidence-szel vagy önbevallás-jelöléssel |
| Arculati választás | felhasználó és Portfolio Designer |
| Komponens | verziózott, biztonságos komponenskatalógus |

Külső linkből metaadat csak szerveroldali URL- és SSRF-ellenőrzés után
olvasható. Privát repositoryhoz vagy szolgáltatáshoz nem kérünk jelszót.

## 3. Rugalmas tartalommodell

A portfólió nem „GitHub mező + n8n mező” szerkezetű. Blokkokból épül:

| Blokktípus | Példa |
|---|---|
| Hero | név, célpozíció, rövid szakmai érték |
| About | hiteles szakmai összegzés |
| Project case study | probléma, szerep, folyamat, megoldás, eredmény |
| Tech/tool list | tetszőleges címkék és kategóriák |
| Link collection | repository, demo, dokumentáció, videó |
| Media | kép, diagram, videó-előnézet |
| Metrics | ellenőrzött számok és mért eredmények |
| Process/timeline | projektlépések |
| Skills/evidence | készség és bemutató projekt kapcsolata |
| Contact | felhasználó által engedélyezett csatornák |

Egy projekt tetszőleges blokkot és linket tartalmazhat. Új eszközhöz nem kell
új adatbázisoszlop.

## 4. Belső részek

1. **Content Studio:** projekt és blokk szerkesztése.
2. **Evidence linker:** portfólióállítást profilhoz/projekthez köt.
3. **Asset pipeline:** képoptimalizálás, fájlellenőrzés és privát tárolás.
4. **Link inspector:** https, domain, átirányítás és SSRF-védelem.
5. **Portfolio Designer:** célhoz illő szerkezet és design-specifikáció.
6. **Design validator:** csak engedélyezett token, komponens és elrendezés.
7. **HTML renderer:** escape-elt adatokból statikus csomagot készít.
8. **Preview sandbox:** izolált előnézet.
9. **Quality checker:** link, reszponzivitás, accessibility és vizuális teszt.
10. **Publisher:** jóváhagyott verziót publikál és visszagörgethetővé tesz.

## 5. Determinisztikus logika és Designer-agent határa

### Portfolio Designer kimenete

```text
PortfolioDesignSpec
  audience
  narrative_order[]
  theme_id
  allowed_layout_ids[]
  project_emphasis[]
  typography_token_set
  color_token_set
  suggested_copy_changes[]
```

Az agent:

- nem ír nyers HTML-t, CSS-t vagy JavaScriptet;
- nem adhat új URL-t vagy projektállítást;
- csak katalógusban létező komponenst, layoutot és designtokent választhat;
- a szövegjavaslatot evidence-hivatkozással adja;
- nem publikálhat.

### Determinisztikus renderelő

- minden felhasználói szöveget escape-el;
- rich textet szűk Markdown/AST allowlistből alakít;
- csak `https` és engedélyezett kapcsolatfajtát fogad;
- tiltja a `javascript:`, `data:` és ismeretlen embed-kódot;
- nem futtat felhasználói scriptet;
- CSP-t, biztonságos linkattribútumot és izolált preview-t állít be;
- ugyanabból a content- és design-verzióból ugyanazt a buildet készíti.

## 6. Adatmodell és API

### Entitások

- `portfolios`: owner, cím, célközönség, aktív verzió.
- `portfolio_versions`: content, design spec, státusz, build hash.
- `portfolio_projects`: owner, cím, szerep, összegzés, sorrend.
- `portfolio_blocks`: projekt/oldal, típus, séma-validált payload, sorrend.
- `portfolio_links`: label, URL, típus, ellenőrzési állapot.
- `portfolio_assets`: privát fájl, alt text, méret, státusz.
- `portfolio_claim_evidence`: állítás és profile/project evidence.
- `portfolio_builds`: renderer-verzió, státusz, quality report.
- `portfolio_publications`: URL, verzió, publikálás és visszavonás ideje.

### API

| Végpont | Feladat |
|---|---|
| `POST /api/v1/portfolios` | portfólió létrehozása |
| `POST /api/v1/portfolios/{id}/projects` | rugalmas projekt hozzáadása |
| `POST /api/v1/portfolios/{id}/blocks` | séma-validált blokk hozzáadása |
| `POST /api/v1/portfolios/{id}/design` | designer-specifikáció készítése |
| `POST /api/v1/portfolios/{id}/builds` | biztonságos előnézet buildelése |
| `GET /api/v1/portfolios/{id}/preview` | saját izolált előnézet |
| `GET /api/v1/portfolios/{id}/quality` | link/a11y/vizuális jelentés |
| `POST /api/v1/portfolios/{id}/publish-request` | pontos publikálási előnézet |
| `POST /api/v1/portfolios/{id}/publish` | jóváhagyott verzió publikálása |
| `POST /api/v1/portfolios/{id}/rollback` | korábbi publikált verzió visszaállítása |

## 7. Eszközök, jogosultságok és jóváhagyások

| Eszköz | Típus | Korlát |
|---|---|---|
| `get_portfolio_content` | adat | saját projekt, minimális profil |
| `inspect_public_link` | determinisztikus read-only | SSRF-védelem, limit |
| `design_portfolio` | Portfolio Designer | komponens- és token-allowlist |
| `validate_design_spec` | determinisztikus | ismeretlen elem blokkolása |
| `render_portfolio` | determinisztikus | escape/CSP/sandbox |
| `run_portfolio_quality` | determinisztikus teszt | link, a11y, responsive, visual |
| `publish_portfolio` | side effect | egyszeri emberi jóváhagyás |

Publikálás előtt az előnézet felsorolja az összes nyilvánossá váló személyes
adatot, fájlt és linket. A jóváhagyás konkrét build hash-re érvényes.

## 8. Kimenet és Career GPS módosítása

Kimenetek:

- szerkeszthető projekt- és tartalommodell;
- célhoz illő, validált design-specifikáció;
- izolált, kattintható HTML-előnézet;
- minőségi jelentés;
- jóváhagyott, verziózott publikáció és visszaállítási pont.

GPS-események: `portfolio_content_ready`, `portfolio_design_approved`,
`portfolio_preview_ready`, `portfolio_published`, `portfolio_unpublished`.

## 9. Hibakezelés és biztonsági tesztek

| Helyzet | Viselkedés |
|---|---|
| Ismeretlen projekt/eszköz | általános blockmodellben rögzíthető |
| Hibás külső link | blokkolt vagy figyelmeztetett, nem embedelt |
| Magánhálózati/localhost URL | SSRF-védelem elutasítja |
| HTML/script a leírásban | escape/sanitize, nem fut le |
| Designer ismeretlen komponenst kér | spec validator elutasítja |
| Hiányzó alt text | quality gate nem enged publikálni |
| Személyes adat nyilvánossá válna | publikálási előnézet külön kiemeli |
| Buildhiba | korábbi publikált verzió változatlan marad |

Kötelező tesztek: XSS-korpusz, veszélyes URL, átirányításos SSRF, túlméretes
asset, törött link, billentyűzetes használat, mobil/desktop screenshot,
vizuális regresszió és rollback.

## 10. Frontend-megjelenés

- Bal oldalon Flow és projektadatok; középen blokkos szerkesztő; jobb oldalon
  élő, izolált előnézet vagy Career GPS.
- Új projekt sablonból vagy üresen indulhat.
- A felhasználó tetszőleges eszközt, linket és projektfajtát vehet fel.
- A Designer 2–3 célhoz illő vizuális irányt ajánl, nem korlátlan véletlen témát.
- Asztali, tablet és mobil preview egy kattintással váltható.
- Minden AI-szövegjavaslat diffként fogadható el.
- Publikálás külön, egyértelmű, nem összetéveszthető gomb.

Az arculat magas szintű, visszafogott és munkáltatói bemutatásra kész; nem
sablonos „AI weboldal” hatású.

## 11. Mérhető elfogadási feltételek

1. Új projekt- vagy eszköztípus adatbázisséma-módosítás nélkül felvehető.
2. Felhasználói HTML, script és veszélyes URL nem hajtható végre.
3. Designer-kimenet kizárólag a komponens- és designtoken-katalógusból választ.
4. Minden szakmai állítás evidence-hez vagy jelölt önbevalláshoz kapcsolódik.
5. Publikálás csak quality gate és konkrét build jóváhagyása után lehetséges.
6. A publikált oldal mobilon és asztali nézetben vizuális regresszión átmegy;
   accessibility célérték legalább 90.
7. Korábbi publikált verzió egy művelettel, auditáltan visszaállítható.
