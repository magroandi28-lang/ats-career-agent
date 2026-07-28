# Az adatbázis állapota — 2026-07-28

Rövid, tényszerű állapotleírás. **Ha változik az adat, ezt is frissíteni kell**,
különben ugyanaz lesz belőle, mint a törölt FOLYTATAS.md-ből: elavult kánon.

A *miért* nem itt van, hanem a migrációk és szkriptek fejléceiben — azok az
adattal együtt frissülnek.

## Mi van bent

| | Darab |
|---|---|
| Valódi állás (`count(distinct tartalom_kulcs)`) | 13 567 |
| Szakma | 555 |
| ESCO-kapcsolattal | 552 |
| KSH-bérrel | 544 |
| Kinyert tétel (`hirdetes_tetel`) | 52 559 |
| ESCO foglalkozás–készség kapcsolat | 126 051 |
| Átjárhatósági pár (`esco_szomszed`) | 56 436 |
| Címkézett tudásanyag-szakasz | 2 448 / 2 735 |
| Cégprofil | 2 118 |

## A három réteg

- **Hirdetések = a mérce.** Mit kérnek, hol, mennyiért. A piac dönt.
- **ESCO = a szótár.** Minek hogy hívják; felismerés, CV-szókincs, átjárhatóság.
  Nem mondja meg, mi értékes.
- **KSH = bérreferencia**, a hivatalos ISCO–FEOR fordítókulcson keresztül.

## Mire tud válaszolni (a valódi állások %-ában)

- Van-e kereslet? — **95,8%**
- Mennyit fizetnek? — **86,0%**
- Mit várnak el? — **84,3%**

A `mv_szakma_lefedettseg` **kérdésenként** ad bizalmi szintet
(`kereslet_bizalom`, `ber_bizalom`, `elvaras_bizalom`). Egyetlen közös jelző
félrevezetne: szakmákat számolva a kép rossznak tűnik (555-ből sok a ritka),
állásokat számolva jó.

## A modell csak ezt látja

`szakma_csomag(szakma_id)` — egy jsonb: adat, forrás, bizalmi szint,
figyelmeztetés. Ami nincs benne, arról nincs mit mondania.

További RPC-k: `cv_illesztes`, `tudas_kereses_temaval`,
`isco_csoport_keszsegei`, `szakma_esco_parositas`, `hirdetes_lattam`,
`hirdetes_lejarat`, `nezetek_frissitese`, `migraciok`.

## Napi működés

**Gyűjtés** — `.github/workflows/jooble_gyujto.yml`, 04:00 UTC:
megyénkénti söprés → EURES → tételkinyerés → adatőr. A söprés a végén beköti
az új szakmákat és lejáratozza az eltűnt hirdetéseket.
**Egyetlen fizetős lépés sincs benne.**

**Karbantartás** — `pg_cron`, 05:30 UTC (`napi-karbantartas`):
tudásanyag-címkézés + minden materializált nézet frissítése.
Ez azért fut az adatbázison belül, mert a Supabase REST-végpontja 8
másodpercnél elvágja a hívást, és ezek a lépések tovább tartanak —
kívülről hívva **csendben kimaradnának**.

## Amit tudni kell, mielőtt bárki nekiáll

- **Nincs ingyenes, teljes szövegű magyar hirdetésforrás.** Mérve: Jooble link
  403, EURES JS-oldal, a Jooble API-nak nincs teljes leírás mezője. A tárolt
  szöveg medián 269 karakter, ezért az elvárás-kinyerés ~34%-on tetőzik. Ez a
  forrás korlátja, nem a kódé.
- **Az ESCO készségneveit nem lehet szövegre illeszteni.** Hirdetésre 32-ből 9
  (zaj), CV-re szigorúan 0. Ezért a `cv_illesztes` javasol, nem állít.
- **A hirdetések 52%-a közvetítőtől jön.** Fluktuációt csak valódi
  munkáltatóra számolunk.
- **A KSH-adat 2024-es, a hirdetések 2026-osak.** Ezt ki kell írni.
- **DDL csak migrációval.** A `scripts/migracio_szinkron.py` összeveti a repót
  az éles naplóval; eltérésnél hibakóddal lép ki, tehát CI-ben fogható.

## Ami hátravan

1. **A témaválasztás bekötése a `backend/flow_contract.py`-ba.** A tudásbázis
   szűrése kész és determinisztikus (`tema_kulcsszo` + tömbmetszet), de azt,
   hogy melyik témára szűrjön, még a hívó dönti el. Az állapotgépből és a
   teszt pontozásából kell jönnie — **nem a modelltől**.
2. **A profession.hu és a Jobline megkeresése** elemzési hozzáférésért. Üzleti
   lépés, nem technikai. Nem blokkol semmit.
3. **Supabase → Authentication → Leaked password protection** bekapcsolása
   (felületi kapcsoló).
