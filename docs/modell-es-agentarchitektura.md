# Modell- és agentarchitektúra

Állapot: **tervezési alap — 2026-07-24**

Ez a dokumentum a [kanonikus felhasználói állapotgép](felhasznaloi-allapotgep.md)
modell- és agentoldali kiegészítése. A vezérlés alapja minden környezetben a
saját determinisztikus orchestrator és állapotgép; az LLM nem orchestrator.

## 1. Környezetek és szolgáltatók

| Környezet | Alapértelmezett szolgáltató | Cél |
|---|---|---|
| helyi fejlesztés, CI, teszt | Gemini | olcsó, gyors fejlesztési iteráció és regresszióteszt |
| staging | Gemini, valamint összehasonlító OpenAI-futás | integráció, golden set és szolgáltatóparitás |
| éles | OpenAI | felhasználói működés, minőségi és üzemi követelmények |

A szolgáltató környezeti változóval váltható:

```dotenv
AI_PROVIDER=gemini
# vagy
AI_PROVIDER=openai
```

Éles környezetben az engedélyezett érték `openai`. Ettől eltérni csak
konfigurációs változtatással, auditált üzemeltetői döntéssel lehet. API-kulcs,
modellazonosító, timeout és kvóta külön titok-, illetve konfigurációkezelésből
érkezik; kliensoldali kódba nem kerül.

## 2. Közös modellinterfész

Az alkalmazás agentjei kizárólag egy szolgáltatófüggetlen `ModelGateway`
interfészt hívnak. A Gemini- és OpenAI-adapter ugyanazt a szerződést valósítja
meg:

```text
generate(
  task_type,
  messages,
  context_refs,
  output_schema,
  model_policy,
  request_limits,
  trace_context
) -> ModelResult
```

A `ModelResult` kötelező mezői: `schema_version`, `data`, `provider`,
`model`, `usage`, `latency_ms`, `finish_reason`, `safety_flags`,
`source_refs`, `request_id` és `error`. A gateway feladata:

- szolgáltató- és modellválasztás a központi policy alapján;
- strukturált kimenet kérése és sémavalidáció;
- timeout, retry, hívásszám- és tokenkorlát alkalmazása;
- személyes adatok minimalizálása és naplózási maszkolása;
- egységes hibakód, metrika és auditmetaadat előállítása.

Az adapter nem alakíthat át hibás választ érvényes domain-döntéssé. Sémán
kívüli, hiányos vagy guardrailt sértő kimenet hiba, és nem okoz
állapotátmenetet.

## 3. Agent-szerződések és eszközjogosultság

| Agent | Feladat | Bemenet | Strukturált kimenet | Engedélyezett eszközök |
|---|---|---|---|---|
| Flow Manager | szándék értelmezése, cél tisztázása, következő lépés javaslata | felhasználói üzenet, aktuális állapot, engedélyezett műveletek, minimális profilösszegzés | `intent`, `confidence`, `clarifying_question`, `proposed_action`, `rationale` | csak olvasó kontextus és műveletjavaslat |
| Career Advisor | forrásolt karrierértelmezés és lehetőségek megfogalmazása | igazolt profil, determinisztikus piaci összesítés, teszt- és tudásbázis-kivonat | `observations`, `options`, `tradeoffs`, `evidence_refs`, `questions` | ellenőrzött profil-, piac- és RAG-olvasás |
| Application Materials Agent | konkrét álláshoz CV- és levéltervezet | kiválasztott hirdetés, igazolt profil, master CV, determinisztikus ATS-eredmény | verziózott `cv_proposal`, `letter_proposal`, állításonként `evidence_refs`, `warnings` | csak olvasás és tervezetkészítés |
| Portfolio Designer | portfólió tartalom- és designspecifikációja | igazolt projektek, célközönség, jóváhagyott tartalom, márka- és hozzáférhetőségi korlátok | `content_plan`, `component_spec`, `asset_refs`, `accessibility_notes` | csak olvasás, előnézet- és specifikációkészítés |

Egy agent sem:

- írhat közvetlenül adatbázist;
- küldhet e-mailt vagy pályázatot, és nem adhat be karrieroldali űrlapot;
- publikálhat portfóliót;
- módosíthatja közvetlenül a Career GPS-t;
- adhat magának új eszközjogosultságot.

Az agent kimenete javaslat. A determinisztikus orchestrator validálja, domain
paranccsá alakítja vagy elutasítja; adatot kizárólag a jogosult
alkalmazásszolgáltatás írhat.

## 4. Modellválasztási politika

Konkrét, dátumfüggő modellazonosítót konfigurációban kell rögzíteni, nem a
domainkódba égetni. A választás feladatosztály és mért evaleredmény alapján
történik.

| Agent | Modellprofil | Elsődleges szempont |
|---|---|---|
| Flow Manager | alacsony késleltetésű, erős többfordulós és strukturált kimenetű modell | szándékpontosság, tisztázási minőség, gyors válasz |
| Career Advisor | erős következtető és hosszú kontextust kezelő modell | forráshűség, árnyalt alternatívák, bizonytalanság jelzése |
| Application Materials Agent | erős írási, utasításkövetési és sémakövetési modell | tényhűség, állításszintű bizonyíték, nyelvi minőség |
| Portfolio Designer | vizuális és strukturált tervezésben erős modell | komponenskonzisztencia, hozzáférhetőség, megvalósítható specifikáció |

Fejlesztésben ezek Gemini-modellprofilokra, élesben OpenAI-modellprofilokra
képeződnek. Modellcsere csak golden set regresszió, költség- és
késleltetésmérés, majd verziózott policy-jóváhagyás után történhet.

## 5. Fallback, timeout és korlátok

- Minden agenthez külön, konfigurált teljes határidő és hívásonkénti timeout
  tartozik; timeout után az orchestrator megszakítja a futást.
- Egy felhasználói lépés hívásszáma és összes bemeneti/kimeneti tokenje
  feladattípusonként korlátozott. A gateway a hívás előtt költséget becsül.
- A napi felhasználói, tenant- és rendszerszintű költségkeret hard limit.
- Automatikus retry legfeljebb egyszer, csak átmeneti szolgáltatói hibára,
  idempotens kérésazonosítóval és rövid jitterrel történhet.
- Ugyanazon szolgáltató kisebb modellje csak alacsony kockázatú
  megfogalmazási feladatra lehet fallback; döntési vagy jóváhagyási
  követelményt nem lazíthat.
- Szolgáltatók közötti automatikus fallback élesben alapértelmezetten tiltott,
  mert adatkezelési és minőségi határt léphet át. Engedélyezése külön,
  auditált incidens-policy tárgya.
- Limit, timeout vagy validációs hiba esetén nincs állapotváltozás. A rendszer
  menthető hibát jelez, és determinisztikus összefoglalót vagy kézi folytatást
  kínál.

## 6. Guardrail, audit és emberi jóváhagyás

A bemeneti réteg a felhasználói, CV-, hirdetés-, web- és RAG-szöveget
megbízhatatlan adatként kezeli. Prompt injection, tiltott tartalom és
személyesadat-túlgyűjtés ellen bemeneti szűrés működik. A kimeneti réteg
sémát, állításonkénti bizonyítékot, tiltott műveletet, személyes adatot és
hallucinált szakmai tényt ellenőriz.

Az auditnapló legalább a következőket tartalmazza: trace- és kérésazonosító,
agent, feladat, provider és modell, prompt-/séma-/policy-verzió, bemeneti
forráshivatkozások, token- és költségadat, késleltetés, guardrail-eredmény,
jóváhagyás-azonosító és domain-esemény. Nyers CV vagy teljes prompt csak külön
indokolt, titkosított és időkorlátos hibakeresési tárolásba kerülhet.

E-mailes küldéshez és karrieroldalas beadáshoz egyszer használható, lejáró,
pontos emberi jóváhagyás kell. A jóváhagyás rögzíti a konkrét állást és céget,
célcímet vagy céloldalt, minden mezőértéket, dokumentumverziót, e-mail-tárgyat
és -törzset, átadott személyes adatot és a végrehajtandó műveletet. Bármely
változás érvényteleníti a jóváhagyást. Az agent nem birtokolhatja és nem
használhatja a végrehajtó tokent.

## 7. Gemini–OpenAI golden set eval

A szolgáltatóparitást verziózott, személyes adatot nem tartalmazó golden set
méri. A készlet lefedi:

- egyértelmű, bizonytalan és összetett Flow-szándékokat;
- CV-feltöltést álláskeresési szándék nélkül;
- konkrét hirdetés nélküli ATS-kérést;
- 0–5 találatos álláskeresési helyzeteket;
- bizonyítékhiányos és ellentmondó profilokat;
- karrier-tanácsadási és pályaváltási eseteket;
- célzott CV-t, motivációs levelet és portfóliótervet;
- magyar és angol nyelvet, prompt injectiont és jóváhagyás-megkerülést.

Minden esethez elvárt struktúra, kötelező és tiltott állítás, bizonyíték,
eszközjogosultság és biztonságos állapotkimenet tartozik. A Gemini- és
OpenAI-futás azonos normalizált bemenetet, sémát és policy-verziót kap.
Automatikus metrikák: sémamegfelelés, intent F1, tény- és hivatkozáshűség,
tiltott műveletek aránya, guardrail recall, késleltetés, token- és becsült
költség. A tanács, pályázati anyag és portfólió vak emberi páros értékelést is
kap. Modell vagy prompt csak akkor léphet tovább, ha minden biztonsági hard
gate teljesül, és nincs elfogadhatatlan minőségi regresszió.

## 8. Kötelező determinisztikus határ

LLM nem számít és nem dönt:

- állásrangsort vagy illeszkedési pontszámot;
- ATS-eredményt;
- piaci mérőszámot, trendet vagy bért;
- felhasználói vagy eszközjogosultságot;
- állapotátmenetet.

Ezeket verziózott szabályok, lekérdezések és programkód számítják. Az LLM
értelmezheti és közérthetően megfogalmazhatja a már kiszámított eredményt, de
nem írhatja felül. A determinisztikus orchestrator minden művelet előtt
ellenőrzi az aktuális állapotot, előfeltételeket, jogosultságot, kvótát,
jóváhagyást és idempotenciát, majd naplózza az eredményt.
