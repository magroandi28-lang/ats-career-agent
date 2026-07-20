# KARRIER-ÜGYNÖKSÉG — FOLYTATÁSI JEGYZET (2026-07-19)

Ez a fájl az új munkamenet indításához készült. Olvasd végig, mielőtt bármihez nyúlsz!

## MI EZ A PROJEKT
Andi álláskeresést segítő Streamlit-alkalmazása (app.py) Supabase-adatbázissal.
Célja: ATS-ellenőrzés, állásra szabott CV+motivációs levél, ÉS valós piaci adatokra
épülő karrier-tanácsadás. A versenyelőny: saját, készség-szintű hirdetés-adatbázis.

## ARCHITEKTÚRA
- **app.py** — Streamlit, 5 fül: 🕵️ Karrier Ügynök (elemez/átír/készít), 🧭 Karrier
  Tanácsadó, 🌟 Portfólió Generátor, 📚 Képzések, ✈️ Külföldi (MÉG PLACEHOLDER).
  Belépő oldal: logo.png (átlátszó), GDPR-szöveg frissítve (Gemini+adatgyűjtés benne).
- **agents/karrier_ugynok.py** — szakma_felismeres (Haiku), allasok_keresese
  (DB-FIRST: előbb friss_hirdetesek a saját DB-ből, ha <5 találat → SerpAPI+scraper),
  ats_diagnozis (Haiku), cv_atiras + motivacios_level (Sonnet, CSAK kérésre),
  keszsegek_kinyerese + skill_gap_elemzes + tanacsado_velemeny (MIND GEMINI, ingyen).
- **agents/ceginfo_agensek.py** — céginfó Google-scrape + Haiku; SZIGORÚ szabály:
  béret TILOS kitalálnia ("Nincs megerősített béradat").
- **utils/adatbazis.py** — teljes Supabase-réteg. FONTOS: osszes_sor() = lapozó
  lekérdezés (a Supabase max 1000 sort ad egyszerre — e miatt volt óriási bug!).
  Fő függvények: gyujtes_mentese (passzív gyűjtés, link-dedup), ceginfo-cache (30 nap),
  friss_hirdetesek (DB-first), szakma_statisztika, szakma_atjaras (v_szakma_fogalmak
  nézetből, min. 3 közös fogalom kell), ksh_kereset (szótő-egyeztetés),
  keszsegnev_normalizalas (determinisztikus, a gyűjtő végén auto-fut), kepzesek_lekerdez.
- **scripts/** — jooble_gyujto.py (NAPI automata: GitHub Actions 04:00 UTC; lapozás
  MAX_OLDAL=3 + SZINONIMAK; Gemini készség-kinyerés; végén auto-normalizálás),
  keszseg_tisztitas.py (Gemini: kanonikus név + tipus; CSAK kanonikus-NULL sorokat
  dolgozza fel → újrafuttatható), keszseg_osszevon.py, keszseg_norma.py,
  kepzesek_feltoltes.py, ksh_import.py (KSH mun0208+mun0206 → piaci_statisztikak).
- **db/** — SQL-ek (sema, tisztitas, fogalmak, nagytakaritas, kepzesek).
- **Supabase**: szakmak, cegek, hirdetesek, keszsegek (nev + kanonikus + fogalom +
  tipus: elvaras/feladat/eszkoz/soft/iparag), hirdetes_keszseg, kepzesek (kurált!),
  piaci_statisztikak (KSH BETÖLTVE: ~500 foglalkozás + megyék). Nézetek:
  v_szakma_attekintes, v_szakma_keszsegek (kanonikus szint), v_szakma_fogalmak
  (fogalom szint — az átjárási térkép ebből számol).
- **GitHub**: github.com/magroandi28-lang/ats-career-agent — minden jó állapot után
  git add . / commit / push. Actions: napi gyűjtés (secrets: JOOBLE, GEMINI,
  SUPABASE_URL, SUPABASE_SECRET_KEY).

## KULCSOK (.env)
ANTHROPIC_API_KEY (CSAK: CV-írás, levél, chat, ATS, szakma-felismerés — kredit ~$0.69,
KÍMÉLNI!), GEMINI_API_KEY (MINDEN adatfeldolgozás, ingyen — NAPI KVÓTA van, 429 =
elfogyott, másnap folytatható), JOOBLE_API_KEY (hu.jooble.org-os kulcs!), SERPAPI_KEY,
SUPABASE_URL, SUPABASE_SECRET_KEY (sb_secret_..., a SERVICE_KEY név is jó).

## ANDI SZABÁLYAI — KÖTELEZŐ BETARTANI
1. EGYSZERRE EGY LÉPÉS. Pontos parancs, szürke kódblokkban. Magyarázat külön, röviden.
2. SEMMIT nem építünk jóváhagyás nélkül. Előbb TERV (a vizuális vázlat bevált!).
3. Minden tartalmi állítás az ADATBÁZISBÓL jön — az AI csak megfogalmaz, SOHA nem
   talál ki (bér, elvárás, céginfó!). "Ez nem nyelvi modell, ez adatbázis-termék."
4. Pénz: cél a 0 Ft. Gemini/determinisztikus megoldás előnyben. Claude csak minőségi
   szöveghez. Költség-meglepetés = bizalomvesztés (egyszer már megtörtént).
5. Munkasablon: 🔧 MIT CSINÁLTAM / 🎯 MIRE JÓ / 👉 A TE DOLGOD / ✅ EZT KELL LÁTNOD.
6. Váltást (átjárást) csak KÉRÉSRE mutat az app — nem tukmálunk.
7. "Kész" csak az, amire Andi mondja, hogy kész.

## ÁLLAPOT + NYITOTT FELADATOK (prioritási sorrendben)
1. **Tanácsadó fül tesztelése** — Andi épp ezt csinálja. Ma került bele: bér-
   normalizálás (havi bruttó Ft-ra átszámítva), KSH-összevetés (hirdetés vs. hivatalos
   átlag + tanács), fogalom-szintű átjárás gombra, körkép-fallback AI nélkül,
   min. 2 előfordulás a cetlikhez, kevés-adat figyelmeztetés.
2. **Külföldi fül TERV** — döntés kell: A1 (angol CV + német Lebenslauf gombra,
   Claude-dal, pár Ft/használat) vagy A2 (elrejtés mára). TERVEZÉS Andival, csak utána kód!
3. **Deploy Streamlit Community Cloud** — élő link kell a portfólióba/LinkedInre.
4. **Portfólió HTML frissítés + LinkedIn szöveg** (HU+EN headline és összefoglaló).
5. **keszseg_tisztitas.py folytatása** — ~2500 sor vár még; Gemini-kvóta visszatöltődés
   után futtatni (magától folytatja, csak a NULL kanonikusúakat dolgozza fel).
6. Később: képzésgyűjtő automata (kurált forrásokból), trend-vizualizáció,
   átjárás bér-szűrője (KSH-val: csak azonos/jobb bérű váltást ajánljon),
   fogalom-réteg finomítás, NFSZ részletes béradat, mappatakarítás.

## ISMERT APRÓSÁGOK
- OneDrive sync-késés: a sandbox néha CSONKA fájlt lát → py_compile OTT hibázhat,
  miközben a valódi fájl jó. Ellenőrzés mindig Andi gépén.
- A logó: logo.png (átlátszó, feldolgozott), logo.jpg az eredeti. Ne cseréld le kérdés nélkül!
- A képzések kurált listája: csak Andi jóváhagyásával bővíthető.

## SZEMÉLYES KONTEXTUS
Andi most szerzett KITÜNTETÉSES (piros) AI-diplomát a Pázmányon. Ruander automata
tesztelő képzés: augusztusban intenzív tanulás, szeptember végén vizsga (portfólió:
a saját appjai tesztelése — Okosmérő és/vagy ez az app). Párhuzamosan pályázni kezd
(cél: AI + tesztautomatizálás metszete). 3 portfólió-projekt: Okosmérő (Dash+CatBoost
energia-előrejelző), Karrier-Ügynökség (ez), n8n email-automatizáció. Fehérvár—Budapest.
Kommunikáció: rövid, lépésenkénti, türelmes, magyarázó — a zsargon és a többfelé futó
instrukciók frusztrálják. Bátorítás jólesik, de csak őszintén.
