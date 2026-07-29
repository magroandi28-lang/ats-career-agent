# Az adatbázis állapota — 2026-07-29

Rövid, tényszerű állapotleírás. **Ha változik az adat, ezt is frissíteni kell**,
különben ugyanaz lesz belőle, mint a törölt FOLYTATAS.md-ből: elavult kánon.

A *miért* nem itt van, hanem a migrációk és szkriptek fejléceiben — azok az
adattal együtt frissülnek.

## Mi van bent

| | Darab | Előző (07-28) |
|---|---|---|
| Valódi állás (`count(distinct tartalom_kulcs)`) | 14 439 | 13 567 |
| Szakma | 677 | 555 |
| ESCO-kapcsolattal | 673 | 552 |
| KSH-bérrel | 544 | 544 |
| Kinyert tétel (`hirdetes_tetel`) | 52 663 | 52 559 |
| ESCO foglalkozás–készség kapcsolat | 126 051 | 126 051 |
| Átjárhatósági pár (`esco_szomszed`) | 56 436 | 56 436 |
| Címkézett tudásanyag-szakasz | 2 448 / 2 735 | 2 448 / 2 735 |
| Cégprofil | 2 151 | 2 118 |

A 07-29-i ugrás egyetlen forrása: **aznap futott le először a teljes,
61 helyszínes megyénkénti söprés** (addig a `main` a régi, 96 kulcsszavas
gyűjtőt futtatta). 8 057 hirdetést látott, ebből 1 710 volt új, 951-et be
tudott sorolni — és ez a 951 hozott 120 új szakmát.

## A három réteg

- **Hirdetések = a mérce.** Mit kérnek, hol, mennyiért. A piac dönt.
- **ESCO = a szótár.** Minek hogy hívják; felismerés, CV-szókincs, átjárhatóság.
  Nem mondja meg, mi értékes.
- **KSH = bérreferencia**, a hivatalos ISCO–FEOR fordítókulcson keresztül.

## Mire tud válaszolni (a valódi állások %-ában)

| | Most | Előző |
|---|---|---|
| Van-e kereslet? | **94,9%** | 95,8% |
| Mennyit fizetnek? | **83,1%** | 86,0% |
| Mit várnak el? | **81,3%** | 84,3% |

**A három szám csökkent, és ez nem romlás.** A nevező nőtt: 120 új szakma jött
be, mind kevés hirdetéssel és KSH-bér nélkül. Ugyanannyit tudunk, csak többről
tudjuk már, hogy létezik. A KSH-bérrel rendelkező szakmák száma változatlanul
544 — a fordítókulcs nem bővült, csak a szakmalista.

A `mv_szakma_lefedettseg` **kérdésenként** ad bizalmi szintet
(`kereslet_bizalom`, `ber_bizalom`, `elvaras_bizalom`; értékei: `eros`,
`gyenge`, `nincs`). Egyetlen közös jelző félrevezetne: szakmákat számolva a kép
rossznak tűnik (677-ből sok a ritka), állásokat számolva jó.

## A modell csak ezt látja

`szakma_csomag(szakma_id)` — egy jsonb: adat, forrás, bizalmi szint,
figyelmeztetés. Ami nincs benne, arról nincs mit mondania.

További RPC-k: `cv_illesztes`, `tudas_kereses_temaval`,
`isco_csoport_keszsegei`, `szakma_esco_parositas`, `hirdetes_lattam`,
`hirdetes_lejarat`, `nezetek_frissitese`, `napi_karbantartas`, `migraciok`.

## Napi működés

**Gyűjtés** — `.github/workflows/jooble_gyujto.yml`, 04:00 UTC:
megyénkénti söprés → EURES → tételkinyerés → adatőr. A söprés láttamozza, amit
lát, beköti az új szakmákat, és a végén lejáratozza az eltűnt hirdetéseket.
**Egyetlen modellhívás sincs benne.**

**Karbantartás** — `pg_cron`, **08:00 UTC** (`napi-karbantartas`):
tudásanyag-címkézés + minden materializált nézet frissítése. Ez azért fut az
adatbázison belül, mert a Supabase REST-végpontja 8 másodpercnél elvágja a
hívást, és ezek a lépések tovább tartanak — kívülről hívva **csendben
kimaradnának**.

**A 08:00 szándékosan van a 04:00-s gyűjtés mögött**, nagy ráhagyással: a
GitHub ütemezője rendszeresen csúszik (2026-07-29-en 04:00 helyett 06:25-kor
indult). Ha a karbantartás a gyűjtés elé csúszna, a nézetek egy napot késnének.

**A lejáratozás NEM a karbantartásban van**, hanem a söprés végén, közvetlenül
a láttamozás után. Fordított sorrendben élő hirdetéseket jelölne eltűntnek.

## Amit tudni kell, mielőtt bárki nekiáll

- **A `letezo_linkek` adagolva kérdez, és ez nem stílus kérdése.** Mérve
  (2026-07-29): 366 link még átmegy, **367-nél `URL component 'query' too
  long`**. Egyetlen hívásban a teljes söprés 15 240 linkje **0 találatot** ad,
  200-as adagokban mind a 15 240-et megtalálja (20,7 s). A régi változat a
  kivételt elnyelte és üres halmazt adott vissza — attól a hívó úgy látta,
  egyetlen hirdetés sincs az adatbázisban: a láttamozás elmaradt. **Egy elnyelt
  hiba itt nem kimaradt lépés, hanem hamis adat.**
- **A `hirdetes_lejarat` halottember-kapcsolóval indul.** Ha 2 napja egyetlen
  hirdetést sem láttunk, `-1`-gyel kilép és nem jelöl semmit. Enélkül egy néma
  gyűjtési hiba két hét alatt kiürítené a piaci képet.
- **Az új hirdetések 44%-át nem lehet besorolni.** Mérve: 1 710 újból 759 nem
  kapott szakmát, mert a címükhöz nincs illeszkedő ESCO-név. Ez a besoroló
  korlátja, nem hiba — de a valódi piac ennél nagyobb, mint amit látunk.
- **Nincs ingyenes, teljes szövegű magyar hirdetésforrás.** Mérve: Jooble link
  403, EURES JS-oldal, a Jooble API-nak nincs teljes leírás mezője. A tárolt
  szöveg medián 269 karakter, ezért az elvárás-kinyerés ~34%-on tetőzik. Ez a
  forrás korlátja, nem a kódé.
- **A Jooble lekérdezésenként korlátoz.** Egy teljes söprés ~8 000 hirdetést
  lát, az adatbázisban 16 000+ van. A különbség nem eltűnt hirdetés — ezért kell
  a 14 napos türelmi idő a lejáratozásban.
- **Az ESCO készségneveit nem lehet szövegre illeszteni.** Hirdetésre 32-ből 9
  (zaj), CV-re szigorúan 0. Ezért a `cv_illesztes` javasol, nem állít.
- **A hirdetések 52%-a közvetítőtől jön.** Fluktuációt csak valódi
  munkáltatóra számolunk.
- **A KSH-adat 2024-es, a hirdetések 2026-osak.** Ezt ki kell írni.
- **DDL csak migrációval.** A `scripts/migracio_szinkron.py` összeveti a repót
  az éles naplóval; eltérésnél hibakóddal lép ki, tehát CI-ben fogható.
  Állapot: 44 migráció, nincs eltérés.

## Ami hátravan

1. **Flow egyetlen szolgáltatása sincs bekötve.** Ma ennyit tud: vendégmód,
   belépés utáni köszöntés, és hogy emlékszik, ki vagy. Onnantól semmit. Az élő
   felület (Next.js/Vercel) a `flow_dontes`-en keresztül beszél — **az pedig
   egyáltalán nem keres a tudásbázisban**: az `input_data`-jában profil, GPS,
   előzmény, állapot és engedélyezett akciók vannak, tudásanyag nincs. Ezért a
   `FlowDecision.evidence_refs` mezőnek ma nincs mire épülnie.
2. **A témaválasztás bekötése.** A `tudas_kereses_temaval` kész és
   determinisztikus (`tema_kulcsszo` + tömbmetszet), de a `utils/flow_agy.py`
   még a vak `tudas_kereses`-t hívja. **Figyelem:** a két hívóhely
   (`flow_kiertekeles`, `flow_valasz`) közül a `flow_valasz` csak a megszűnt
   Streamlit `app.py`-ból érhető el. Önmagában a szűrő bekötése tehát olyan
   kódutat javítana, amit az élő alkalmazás nem használ — az 1. ponttal együtt
   van értelme. A témát az állapotgépnek (`CareerState`/`CareerIntent`) és a
   teszt `jollet_jelzes()`-ének kell adnia, **nem a modellnek**.
3. **A repó nincs kitakarítva.** A Streamlit-korszak kódja (`app.py`,
   `templates/`, a `/flow-kiertekeles` végpont) még bent van, keveredik az új
   Next.js/Vercel felépítéssel. Ez nem hiba, de félrevezeti azt, aki
   most néz rá a kódra — ahogy engem is félrevezetett.
4. **A profession.hu és a Jobline megkeresése** elemzési hozzáférésért. Üzleti
   lépés, nem technikai. Nem blokkol semmit.
5. **Supabase → Authentication → Leaked password protection** bekapcsolása
   (felületi kapcsoló).
