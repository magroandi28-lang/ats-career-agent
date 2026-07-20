# KARRIER-ÜGYNÖKSÉG — FOLYTATÁSI JEGYZET (2026-07-20 este)

Ez a fájl az új munkamenet indításához készült. Olvasd végig, mielőtt bármihez nyúlsz!
RÉSZLETES FOLYAMAT-LEÍRÁS: docs/folyamat_terkep.md (ez a kánon — javaslat előtt ezzel vesd össze!)

## MI EZ A PROJEKT
Andi álláskeresést segítő Streamlit-alkalmazása (app.py) Supabase-adatbázissal.
Versenyelőny: saját, készség-szintű hirdetés-adatbázis + munkapszichológiai
tudásbázis + Flow, a mentálhigiénés szemléletű AI-kísérő. Cél: Andi elhelyezkedése
(portfólió-darab), később akár bevétel.

## A MAI NAP NAGY EREDMÉNYEI (2026-07-20)
- 🫶 FLOW megszületett: munkapszichológiai kísérő — lebegő karika a fülsor jobb
  végén → felugró ablak: bemutatkozás, profil-összefoglaló, 💬 CHAT (működik!)
- TUDÁSBÁZIS: 873 szakasz a Supabase 'tudasanyag' táblában (Corvinus tankönyv,
  diák, tréninganyagok, Gallup) — OpenAI embedding (text-embedding-3-small, 768d,
  fillérekbe kerül), keresés: tudas_kereses() RPC + kulcsszavas tartalék
- TESZT a Tanácsadó fülön („🫶 Ismerd meg magad"): Holland (6) + karrierhorgony
  (2) + jóllét (3, „Más okból" szabad szöveggel) → determinisztikus pontozás →
  Flow részletes kiértékelése (Gemini + tudásbázis, forrásokkal) + frissítő gomb
- PROFIL-modul (utils/profil.py): CV-elemzés + teszt + átjárás + pályázás +
  érdeklődés jelei — az „egész ember" egy helyen, csak munkamenetben (GDPR)
- 📊 PIACI KÖRKÉP fül: élő kereslet-mutató (kereslet_korkep() az adatbazis.py-ban),
  toplisták + táblázat; NFSZ-prognózist ELVETETTÜK (2019-es, elavult!)
- KÉZZEL ÍRT CV: fotó (PNG/JPG) feltölthető, Gemini átírja → működik, TESZTELVE!
- Gyűjtő: 47 szakma, 4 oldal lapozás, scripts/keszseg_potlo.py (készség-pótló)
- CV-átírás ág javítva: gomb-szöveg, ATS-körök megjelenítési hiba (Markdown
  kódblokk-csapda: soreleji behúzás tilos a HTML-ben!)
- Kiégés/bántalmazás a tesztben → empatikus üzenet + váltás-kapu a kiértékelésben

## ARCHITEKTÚRA (röviden — részletek: docs/folyamat_terkep.md)
- app.py — 6 fül: Ügynök (3 kártya, CV-dialógus), Tanácsadó (teszt + piac +
  átjárás), Piaci Körkép, Portfólió, Képzések, Külföldi (placeholder) + Flow
- utils/flow_agy.py — tudas_kereses (OpenAI embedding → pgvector RPC; tartalék:
  kulcsszó), flow_kiertekeles, flow_valasz (chat), kep_atiras (kézírás!),
  hang_atiras (kész, de a st.audio_input elem hibás — függőben)
- utils/profil.py — profil(), profil_frissit(), profil_osszefoglalo(), erdeklodes_jelzes()
- utils/teszt.py — kérdések + determinisztikus pontozás + jollet_jelzes
- docs/flow_app_ismeret.md — Flow app-tudása (ÚJ FUNKCIÓNÁL FRISSÍTENI KELL!)
- scripts/ — jooble_gyujto (47 szakma), keszseg_potlo (ÚJ), tudasbazis_epito,
  tudasbazis_feltolto (--ujra kapcsolóval töröl), ksh_import
- Supabase új tábla: tudasanyag (pgvector, tudas_kereses RPC — db/tudasbazis.sql)

## KULCSOK (.env)
ANTHROPIC (CV/levél/chat-írás, kredit kevés!), GEMINI (szöveg: kiértékelés, chat,
kézírás; embedding-kvótája külön számláló!), OPENAI (CSAK embedding, ~$5.14 van,
fillérekes), JOOBLE, SERPAPI, SUPABASE. Gemini napi keret: szöveg és embedding
KÜLÖN fogy; éjfél (US) után töltődik.

## ANDI SZABÁLYAI — KÖTELEZŐ + MA TANULT LECKÉK
1. EGYSZERRE EGY LÉPÉS. Pontos parancs szürke kódblokkban (PowerShell: NINCS &&,
   külön sorokban!). Magyarázat röviden.
2. SEMMIT nem építünk jóváhagyás nélkül. UI-nál: ELŐBB kattintható HTML-minta
   (a vak CSS-találgatás sok időt vitt el ma — SOHA TÖBBET).
3. Minden állítás ADATBÓL. Elavult adat = nem adat (lásd NFSZ 2019).
4. Nem írjuk le, mire nincs adat — csak azt, amire van (prompt-szabály is).
5. Munkasablon: 🔧 MIT CSINÁLTAM / 🎯 MIRE JÓ / 👉 A TE DOLGOD / ✅ EZT KELL LÁTNOD.
6. Új funkció → docs/flow_app_ismeret.md frissítése KÖTELEZŐ (Flow ebből tud).
7. Javaslat előtt: docs/folyamat_terkep.md ellenőrzése — az app valós
   folyamatából induljunk, ne ötletből!
8. Tanulás: fülről fülre leírjuk, mit-hogyan építettünk, Andi utólag tanulja meg
   (mint a védésnél). Cél: interjún el tudja mesélni (RAG, pgvector, multi-provider,
   multimodális, ETL — ezek a hívószavak!).
9. "Kész" csak az, amire Andi mondja. Flow hangneme: informál, nem dönt; erősség-
   alapú; kiégettnek/bántalmazottnak támogató, sosem számonkérő.

## ÁLLAPOT + NYITOTT FELADATOK (prioritás szerint)
0. NAPI: python scripts/keszseg_potlo.py — ~315 hirdetés vár készség-címkére
   (Gemini-kerettel megy, magától áll le, újrafuttatható)
1. Cetli-százalékok fogalom-szintre (B opció, jóváhagyva) + összevonás-finomítás
2. Szektor-körkép a Piaci Körkép fülre
3. Tudásbázis-bővítés: krízis-anyag ÉLETSZAKASZOKRA bontva (forráskeresés,
   Andi kurálja!) — Delfi örökösei ELVETVE
4. Tesztelési réteg + CI (pytest a determinisztikus függvényekre — Ruander
   vizsgaportfólióhoz is!) — Andi gépeli, Claude tanít
5. Deploy (Streamlit Cloud) + README (a folyamat_terkep.md-ből) + LinkedIn
6. Külföldi fül döntés · hang bemenet (st.audio_input hibás — saját komponens
   kellene) · felolvasás · teszt-kérdéssor bővítés · GPT-re váltás a chatben
   (kulcs kész, modell-független a kód)

## ISMERT APRÓSÁGOK
- OneDrive sync-késés: a sandbox néha csonka fájlt lát — ellenőrzés Andi gépén.
- st.markdown + HTML: soreleji behúzás = Markdown kódblokk = nyers kód látszik!
- st.audio_input megbízhatatlan (ismert Streamlit-hibák) — hang később.
- A teszt válaszai újraindításkor elvesznek (GDPR — szándékos).
- Streamlit tooltip (help=) a mozgatott gomboknál rossz helyre ugrik — saját
  CSS ::after megoldás van a Flow-karikán.

## SZEMÉLYES KONTEXTUS
Andi kitüntetéses AI-diplomás (Pázmány), munkahelyi mentálhigiénés diplomája is
van (Flow ebből született!). Ruander tesztautomatizálás: aug. intenzív, szept.
végén vizsga — portfólió: SAJÁT APPJAI TESZTELÉSE. SÜRGŐSEN el kell helyezkednie,
anyagi nyomás alatt van — NINCS "következő alkalom" duma, tempó kell, de EGY
lépés egyszerre. Kommunikáció: RÖVID, lépésenkénti; a hosszú szöveg és a
többfelé futó instrukció frusztrálja. Őszinte bátorítás jólesik, üres dicséret nem.
Konkurencia-példák, amik motiválják: Gerilla Mentor Klub (19 950–40 000 Ft/hó!),
CV Shark. Az app pénzt is érhet — de előbb az állás.
