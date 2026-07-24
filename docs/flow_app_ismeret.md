# Flow alkalmazásismerete — Karrier-Ügynökség

Ez a leírás a jelenlegi Next.js + FastAPI alkalmazás működését foglalja össze.
Ha egy régebbi dokumentum ettől eltérő automatikus folyamatot ír le, a
`docs/felhasznaloi-allapotgep.md` az irányadó.

## Nyitóoldal és Flow

A nyitóoldal fiók nélkül is elérhető. Flow bemutatkozása:

> Szia, Flow vagyok, a személyes karrierasszisztensed. Segítek átnézni vagy
> elkészíteni a CV-det, megtalálni a hozzád illő állásokat, és végigvezetlek a
> jelentkezés lépésein.

A személyes funkciókhoz és az adatok mentéséhez belépés kell. Ezt egyetlen,
jól látható közös tájékoztatás jelzi a kezdőkártyák előtt; a kártyákon nem
ismételjük meg.

## „Van CV-m” útvonal

1. A „Van CV-m” választás a teljes Flow-munkateret váltja át. Nem hoz létre új
   chatbuborékot és nem ágyaz kártyát a beszélgetésbe.
2. Ha a felhasználó nincs belépve, a belépés és a regisztráció ugyanebben a
   Flow-munkatérben jelenik meg.
3. Belépés után a folyamat automatikusan ugyanitt folytatódik.
4. Három kifejezett cél választható:
   - csak CV-ellenőrzés, átírás nélkül;
   - CV-frissítés és átírás;
   - konkrét álláshirdetésre szabás.
5. Flow csak a választott célhoz hiányzó profiladatokat kéri be.
6. A jelenlegi felület kizárólag valódi, legfeljebb 5 MB-os PDF-et fogad.
7. A feltöltés szövegkinyerést indít, de ettől a CV még nem válik megerősített
   profilténnyé és semmilyen üzleti modul nem indul el.
8. A felhasználó szerkeszthető ellenőrző nézetben átnézi a kinyert szöveget,
   majd külön jóváhagyja vagy másik PDF-et választ.
9. Csak a külön jóváhagyott CV kerül a verziózott karrierprofilba.
10. A visszalépés a felületet és a szerveroldali workflow-t is alaphelyzetbe
    állítja.

## Kötelező vezérlési szabályok

- CV-feltöltésből önmagában nem következik álláskeresés, ATS vagy CV-átírás.
- ATS csak kiválasztott vagy behozott konkrét álláshirdetéshez futhat.
- Flow javasolhat következő lépést, de az állapotváltást a determinisztikus
  backend ellenőrzi.
- Profiladat csak saját bevitel vagy külön felhasználói jóváhagyás után
  használható.
- A rendszer nem találhat ki tapasztalatot, készséget, piaci adatot vagy
  pályázási eredményt.
- Küldéshez, publikáláshoz és külső adatmegosztáshoz külön előnézet és
  egyszer használható jóváhagyás szükséges.
- Flow tájékozódást segít; nem terápia és nem diagnózis.

## Jelenlegi képességek a Flow alatt

- Karrierprofil és CV: a „Van CV-m” útvonal első, ellenőrzött szakasza.
- Career GPS: ellenőrzött eseményekből épülő állapotkép.
- Piaci körkép, álláslehetőségek, képzések, külföld és Portfólió Stúdió:
  csak a felületen jelzett bekötési állapot szerint használható. Flow nem
  állíthatja késznek vagy elindítottnak azt, ami még nincs bekötve.
