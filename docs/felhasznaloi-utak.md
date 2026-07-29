# Felhasználói utak — a teljes lefedettség

Ez a doksi azt rögzíti, **hány különböző helyzetből érkezhet valaki**, és
mindegyikre mi a folyamat. Nem képernyőterv: azt mutatja meg, mit kell
tudnia a rendszernek ahhoz, hogy senki ne akadjon el.

**A terv úgy készült, mintha minden adatforrás megvolna.** Ahol ma hiányzik
(képzések), ott a lépés akkor is szerepel — csak a tesztelése vár. A terv
ne igazodjon egy ideiglenes adathiányhoz.

## Miért nem lista, hanem tábla

Négy-öt „változatot" felsorolni mindig hiányos lesz. Két dimenzió van, ami
ténylegesen megváltoztatja, mit csinál a rendszer; a kombinációik adják ki a
teljes képet.

**A) Milyen adatunk van róla**

1. Van CV-je
2. Nincs CV-je, de el tudja mondani
3. Csak végzettsége van (nincs munkatapasztalat)

**B) Mit tud a céljáról**

1. Nem tudja, mit akar
2. Ugyanaz a szakma, mint eddig (munkahelyet vált, nem pályát)
3. Más szakma (pályaváltás)

Ez 3 × 3 = **kilenc eset**. Plusz egy tizedik, ami átvágja a táblát: akinek
**már van egy konkrét hirdetése** — nála a célszakma magából a hirdetésből
jön, tehát a B dimenzió nem kérdés.

## ALAPSZABÁLY: egy kártya egy zárt folyamat

Ez a legfontosabb, és eddig ezt sértettük meg. A kártyák **nem futnak
egymásba**. Aki a CV-átvizsgálást választja, az a CV-átvizsgálást kapja —
és amikor kész, **véget ér**. Nem nyílik meg mellette a piaci körkép, az
álláskeresés és a tanácsadás.

Mérve: a CV-átvizsgálás közben három további kártya jelent meg, és a
folyamat használhatatlanná vált tőle.

Amit Flow tehet a végén: **megkérdezi**, hogy megnézzük-e a piaci képet is.
Kérdés, nem kártyaeső. Ha igent mondasz, az már a következő folyamat.

## Mit ad EGY kártya, elejétől a végéig

| Kártya | Mit csinál | Mivel ér véget |
|---|---|---|
| **Van CV-m** | CV beolvasása → célmunkakör választása a CV-ből → formai szűrő → szókincs → emlékeztető | „Ez a CV-d állapota." |
| **Nincs CV-m** | rövid interjú → célmunkakör → CV összeállítása igazolt tényekből | „Kész a CV-d." |
| **Pályát váltanék** | célszakma megadása → átjárhatóság (mi a közös) → készséghiány → **képzés a hiányra** | „Ennyi az út a célig." |
| **Teszt** | kérdőív → érdeklődés, karrierhorgony, jóllét → **javasolt célszakmák** | „Ezek illenek hozzád." |
| **Piaci körkép** | célszakma → kereslet, bér, elvárások, bizalmi szint | „Így áll a szakmád a piacon." |
| **Állást keresek** | célszakma → találatok, illeszkedés szerint | „Ezeket találtuk." |
| **Portfólió** | önálló, a többitől független | |

Minden kártyához kell **egy célszakma** — kivéve a Tesztet, ami éppen azt
állapítja meg, és a „Nincs CV-m"-et, ami menet közben kérdezi meg.

**A célszakma nem azonos a pályaváltással.** Aki bolti eladó és bolti eladó
munkát keres máshol, annak a célszakmája bolti eladó. Mindenkinek van
célszakmája; a különbség csak annyi, hogy a CV javaslata jó-e neki.

Ha valaki olyan kártyát választ, amihez még nincs célszakmája, Flow egyetlen
kérdést tesz fel — „mire keressek?" —, és mehet tovább. Nem küldjük másik
kártyára.

## A képzés helye

A képzés nem különálló szolgáltatás, hanem a 3. lépés készséghiány-számításának
egyenes következménye. Ugyanaz a számítás adja, ami az átjárhatóságot:

- **Mit kell megtanulnod** — a célszakma ESCO-készségei mínusz amit a CV
  igazol. Ez ma is számolható.
- **Hol tanuld meg** — a `kepzesek` táblából. Ma 12 sor van benne, tehát ez
  a fele még nem tesztelhető.

A tervben mindkettő szerepel. Amíg a forrás hiányzik, Flow mondja ki
őszintén: „ez a négy dolog hiányzik; képzési ajánlatunk erre még nincs, de
már tudod, mit keress."

## Kártyák és belépési pontok

Egy kártya = egy belépési pont ugyanabba az útba.

| Kártya | Hol lép be |
|---|---|
| Van CV-m | 1. lépés, CV-vel |
| Nincs CV-m | 1. lépés, interjúval |
| Pályát váltanék | 2. lépés, más céllal |
| Teszt | 0. lépés, ha nem tudja a célt |
| Piaci körkép | 3. lépés, ha csak tájékozódik |
| Állást keresek | 4. lépés |
| Portfólió | önálló, a többitől független |

Aki az „Állást keresek"-kel kezd, de nincs célszakmája, azt nem utasítjuk
el: Flow egyetlen kérdést tesz fel — „mire keressek?" —, és mehet tovább. Ez
nem pályaváltás-kérdés, csak annyi, hogy tudjuk, mit keresünk.

## Mi működik ma ebből

A kilenc cellából **egyet** tudunk végigvinni: **van CV + ugyanaz a szakma**.

| Hiányzik | Mihez kell |
|---|---|
| Interjú | a „nincs CV" és a „csak végzettség" sorhoz |
| Teszt bekötése | a „nem tudja, mit akar" oszlophoz (a kódja megvan a régi oldalról) |
| Átjárhatóság mint lépés | a „más szakma" oszlophoz (az adat megvan a `szakma_csomag`-ban) |
| Készséghiány-számítás | a képzéshez és a pályaváltáshoz |
| Képzési forrás | a képzés második feléhez (ma 12 sor) |
| Portfólió | önálló kártya |

## Amit ki kell mondani a felhasználónak

- **A „csak végzettség" sorban kevés az adat.** A piaci körkép is gyengébb
  lesz, mert nincs mihez kötni. Ezt jelezni kell, nem elhallgatni.
- **A CV neve és a fiók neve két külön dolog.** A megszólítás a fiókból jön,
  sosem a dokumentumból: a CV egy elemzendő irat, nem személyazonosság.
- **A célmunkakör nem azonos a jelenlegivel.** A CV azt mondja meg, mi VOLT.
  A döntés a felhasználóé, ezért a rendszer javasol, nem állít.
