# Karrier Ügynök fül — automatizált folyamat terve

Ez a dokumentum a 2026.07.22-i tervezőbeszélgetés eredménye. Célja: mielőtt bármi
megépül a React/Next.js frontenden, itt legyen leírva, MIT és MIÉRT építünk —
hogy semmi ne vesszen el, és bármikor visszanézhető legyen.

Ez a terv a Karrier Ügynök fület érinti (a régi Streamlit `app.py`-ban az első
fül, 3 kártyával: "Van CV-m — nézd át" / "Van CV-m — írd át" / "Nincs CV-m").
A régi Streamlit app ettől függetlenül, változatlanul tovább fut és
használható — ez a terv csak az ÚJ, React-es verzióra vonatkozik.

## Alapelv

A rendszer attól "automatizált", hogy nem kell fület-gombot-fület kattintgatni
minden lépéshez — de ettől még minden LÉNYEGI döntés (kire pályázzon,
milyen irányba menjen) a felhasználónál marad. Az automatizálás a felesleges
kattintgatást szünteti meg, nem a felhasználó döntési jogát.

## Belépési pont: Flow fogad mindenkit (ÚJ, ma döntött)

Az oldal betöltésekor NEM egy 6 fülből álló menüt lát a felhasználó, amiből
magának kell kitalálnia, hova kattintson. Flow fogadja, természetes nyelven
megkérdezi mire van szüksége (pl. "hova pályáznál", "min szeretnél
segítséget kapni"), és a válasz alapján Ő dönti el, melyik fület/folyamatot
javasolja és indítja el az adott embernek — a felhasználónak nem kell
ismernie a fülek neveit/tartalmát ahhoz, hogy eljusson a megfelelő helyre.

Ez azt jelenti, hogy a 0. lépés (lásd lent: "milyen szakmában keresel
állást") gyakorlatban Flow beszélgetésének RÉSZE lesz, nem egy külön,
elszigetelt űrlapmező — Flow természetes beszélgetésben szedi ki ezt is,
és a beszélgetés alapján irányít tovább a Karrier Ügynök automatizált
láncába (vagy másik fülre, ha az illetőnek más kell: tanácsadás, piaci
körkép, portfólió, képzés, külföld).

Fontos pontosítás (ma döntött): a fülek NEM láthatók statikus menüként.
A felület nem egy 6 gombos tabsorral indul — csak az az EGY rész jelenik
meg, amire az adott embernek ténylegesen szüksége van, Flow döntése
alapján (pl. ha valaki csak tanácsot kér, a Tanácsadó-rész jelenik meg; ha
pályázni is szeretne, a Karrier Ügynök lánca). A többi rész nem látszik,
amíg nincs rá szükség.

Flow személyisége: a cél, hogy Flow ne egy semleges, robotikus asszisztens
legyen, hanem alapból meleg, empatikus, segítőkész hangnemű — ez a
rendszerprompt gondos megírásán és az erősebb konverzációs modellen múlik
(lásd "Flow szerepe" rész lent). Ez tervezhető és nagyrészt elérhető cél,
de AI-nál sosem 100%-ban garantálható minden helyzetben.

Konkrét felület (ma pontosítva): Flow egy saját, szép beszélgető-panelben
jelenik meg (nem apró felugró buborék). Bemutatkozik írásban (a hang
opcionális kiegészítés, nem kötelező minden ponton). A bemutatkozás után
KÉT út áll nyitva egyszerre:
1. Gyors választógombok a leggyakoribb esetekre (pl. "Állást keresnék",
   "Csak tanácsot szeretnék", "Külföldre mennék", "Portfóliót készítenék")
   — egy kattintás, nincs szükség megfogalmazásra.
2. Szabad szöveg/hang — a felhasználó a saját szavaival leírja/elmondja,
   mire van szüksége.

Bármelyik úton is dönt a felhasználó, Flow UGYANABBAN a beszélgető-
felületben jeleníti meg a megfelelő szolgáltatás-részt (pl. a Karrier
Ügynök láncát) — nem külön oldalra navigál át, hanem a beszélgetésen belül
"húzza be" a megfelelő eszközt, megszakítás nélkül.

TILTOTT MINTA (ma explicit kizárva, Andi rossz Telekom-chatbot élménye
alapján): a gyors választógombok SOSEM lehetnek az egyetlen út. Ha a
felhasználó valami olyat ír/mond, ami nincs a felkínált gombok között,
Flow-nak akkor is értenie kell és válaszolnia kell rá — nem terelheti
vissza egy "ezt nem értem, válassz a listából" típusú válasszal. A gombok
csak kényelmi rövidítések a leggyakoribb esetekhez, nem korlátok.

Fontos hatókör-pontosítás: ez a teljes tervdokumentum egyelőre KIZÁRÓLAG a
Karrier Ügynök fület dolgozza ki részletesen Flow-val összekötve. A "Flow
fogadja az egész oldalon mindenkit és irányít a többi fülre is" a
távolabbi, nagyobb irány — ennek részletes kidolgozása külön, későbbi
tervezés tárgya lesz, most nem ez épül meg elsőként.

## 0. lépés — kötelező, mindenkitől (ÚJ, ma döntött)

A CV szövege csak azt mutatja meg, HONNAN jön valaki (végzettség, eddigi
munkahelyek) — azt, HOVA szeretne menni, a CV-ből soha nem lehet biztosan
kitalálni. Ezért ez a kérdés mindenkitől, elsőként, kötelezően elhangzik,
függetlenül attól, van-e CV-je vagy sem:

> "Milyen szakmában/pozícióban keresel most állást?"

Ezt NEM a CV szövegéből következteti ki a rendszer (ez volt a régi
viselkedés, ha üres volt a `szakma_megadva` mező) — ez mostantól mindig
explicit, direkt kérdés, akár szöveggel, akár hangban válaszol rá a
felhasználó (lásd hang-részt lent).

## 1. lépés — CV megadása (opcionális) + automatikus triázs

A felhasználó feltölthet CV-t, vagy jelezheti hogy nincs. Ha van CV, a
rendszer MAGA dönti el (nem a felhasználó önbevallása alapján!), hogy ez
"csak átnézendő" szintű, vagy valójában "újraépítendő":

Elavultság-jelek, amiket a rendszer megnéz:
- születési dátum / családi állapot / fénykép-utalás szerepel-e benne
  (régimódi magyar CV-hagyomány, amit a mai ATS-ek/HR-esek negatívan
  értékelnek)
- mennyire régi a legutóbbi munkatapasztalat dátuma
- mennyire fedi le a CV a cél-szakmához tartozó, ma elvárt kulcsszavakat
  (ha átfogóan hiányoznak, nem csak pontszerűen, az inkább elavultságra utal,
  nem egy-két hiányzó szóra)

Ha a CV elavultnak minősül, a felhasználó a mélyebb, újraépítős úton megy
végig akkor is, ha technikailag feltöltött egy CV-t — nem hagyatkozunk arra,
hogy ő maga jól ítéli-e meg a saját CV-je állapotát (lásd: "20 éve egy
helyen, kiégett, fogalma nincs mi a trend" eset).

## 2. lépés — automatikus, ingyenes lánc (kattintás nélkül fut)

Ezek MIND meglévő, letesztelt backend-végpontok, csak eddig külön kellett
hívni őket. Most egyben, automatikusan futnak, a 0. lépésben megadott cél
alapján:

1. szakma felismerése (a megadott cél alapján, NEM a CV-ből kikövetkeztetve)
2. ATS-diagnózis (determinisztikus, valós adatbázis-adatból — `szakma_statisztika`)
3. 5 legjobb állás megkeresése és rangsorolása (determinisztikus,
   `allasok_rangsorolasa_determinisztikus`)

Ez a rész teljesen ingyenes (nincs benne AI-hívás, vagy ha van, elhanyagolható
költségű), ezért nincs ok arra, hogy a felhasználó lépésről lépésre
kattintgassa végig.

## 3. lépés — felhasználói döntés (ITT marad a kontroll)

Az 5 találatból a felhasználó kiválasztja (bejelöli), melyikre/melyekre
szeretne pályázni — lehet 1, néhány, vagy mind az 5. Ez szándékosan NEM
automatikus, mert csak ő tudja, melyik cég/pozíció érdekli ténylegesen.

## 4. lépés — automatikus generálás a kiválasztottakhoz

A kiválasztott (akár mind az 5) hirdetéshez automatikusan elkészül a CV-átírás
és a motivációs levél — mindegyik a KONKRÉT hirdetés szövegéhez igazítva
(nem általános, "szakmának szóló" szöveg). Ez már ma is így működik a
`/cv-atiras` és `/motivacios-level` végpontnál (egy konkrét `allas` objektumot
várnak), csak eddig egyenként kellett hívni — mostantól a kiválasztott
összeshez egyszerre fut le.

Döntés: a költség (kb. néhány forint hívásonként) elhanyagolható ahhoz
képest, amennyi időt/esélyt spórol a felhasználónak, ha egyszerre több kész
anyagot kap — ezért NEM korlátozzuk automatikusan csak a legjobb találatra.

## Extra jelzés: "már jelentkeztem, nem hívtak vissza"

Ezt a CV nem tudja elárulni (ez a felhasználó fejében van, nem a szövegben).
Opcionális mezőként hozzáadható, hogy Flow ezt is figyelembe tudja venni a
tanácsadásnál — de a rendszer nem próbálja ezt kitalálni/feltételezni.

## Perszónák, amiket a tervezésnél figyelembe vettünk

- Frissen kiégett, régóta egy helyen, váltani akar, nem ismeri a trendet
  → újraépítős út, akkor is ha technikailag van CV-je
- Pályakezdő, alig van tapasztalata → "nincs CV-m" út
- Aktívan pályázó, korszerű CV, mégsem hívják be → valódi ATS-finomhangolás
- Szakmát/iparágat váltó → skill-gap elemzés + áthidalás, nem csak CV-szöveg
- Elbocsátott, azonnal kell állás → sebesség/mennyiség előtérbe helyezése
  (ez erősíti a "mind az 5-höz anyag" döntést)
- Van CV, pályázott, csend, de nem biztos hogy CV-probléma (interjú-technika,
  piaci túlkínálat) → a rendszer őszintén jelezze, ha nem biztos hogy a CV a
  gond, ne ígérjen mindenre megoldást

## Flow szerepe

- Természetes nyelvű rákérdezés bizonytalan/hibrid esetekben (pl. "AI
  szakértő és automata tesztelő" — melyik irányba menjen a keresés)
- Hangalapú bevitel/kimenet: böngésző beépített Web Speech API-ja
  (SpeechRecognition + SpeechSynthesis) — INGYENES, nincs API-költség,
  Chrome-ban natívan működik. Ez a Streamlit-ben korábban nem volt
  megbízhatóan megoldható (`st.audio_input` ismert hibái miatt) — ez az
  új frontend egyik valódi, konkrét előnye. Begépelés mindig marad tartalék
  lehetőségként, ha a hangfelismerés nem ért meg valamit.
- Konverzációs minőség: a beszélgetős részekhez (nem a pontszámításhoz —
  az marad kódos/determinisztikus) erősebb AI-modell + szabadabb,
  kevésbé mereven strukturált prompt, hogy Flow természetesebben,
  "okosabban" hasson beszélgetés közben.

## Amit ez a terv NEM módosít

- A régi Streamlit `app.py` és a mögötte lévő `agents/`, `utils/` logika
  változatlan, párhuzamosan tovább fut.
- A determinisztikus számítások (ATS %, állás-rangsorolás) kódban maradnak,
  nem AI-becslés — ez már korábban eldöntött, nem változik.

## Megvalósítva (2026.07.22, ma este)

Az első, valódi verzió elkészült és lokálisan letesztelve (`npm run build`
hibamentes):
- `frontend/src/app/page.js`: Flow beszélgető-panel a belépési pont —
  bemutatkozás, gyors gombok ("Állást keresnék" stb.) + szabad szöveges
  mező, meglévő `/flow-chat` végponthoz kötve.
- `utils/flow_agy.py`: `flow_valasz()` promptja kiegészítve két új résszel
  (`FLOW_SZEMELYISEG`, `FLOW_IRANYITAS`) — Flow felismeri az álláskeresési
  szándékot, megkérdezi a célszakmát, ha nem tudja, és `[FLOW_AKCIO:
  karrier_ugynok:SZAKMA]` jelöléssel jelzi a frontendnek, mikor indítsa el
  a keresést.
- `frontend/src/app/KarrierUgynok.js`: a korábbi keresőoldal kiszervezve
  komponensbe, `kezdoSzakma` propon keresztül Flow automatikusan el is
  indíthatja, kattintás nélkül.

Amit ez MÉG NEM tartalmaz (későbbi kör): hangalapú be/kimenet, a mind-az-5-
höz CV+levél generálás és kiválasztás, elavultság-alapú triázs, a többi
fülre irányítás.

## Következő lépés

Ha ez a terv jóváhagyva, a tényleges építés sorrendje:
1. `/szakma-felismeres` hívás mindig a 0. lépésben megadott céllal (nem
   CV-ből kikövetkeztetve) — apró backend-pontosítás.
2. Elavultság-jelző hozzáadása az ATS-diagnózishoz (új, még nem létezik).
3. React-oldal: 0-4. lépés összefűzve, checkbox-os kiválasztással.
4. Hangalapú be/kimenet hozzáadása (böngésző API).
5. Flow konverzációs promptjának/modelljének erősítése.
