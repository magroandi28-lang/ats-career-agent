-- Utólag mentve az éles migrációs naplóból (20260728182357).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A régi készségcímke-lánc befagyasztása. NEM TÖRLÉS.
--
-- Két párhuzamos rendszer élt ugyanarra a kérdésre: a régi címkelánc
-- (`keszsegek` 7 399 sor, ebből 1 711-nél nincs kanonikus és 1 884-nél nincs
-- fogalom; `hirdetes_keszseg` 23 440 sor) és az új `hirdetes_tetel`. A kód
-- már az újat használja. Amíg mindkettő él, két különböző igazság van.
--
-- Nem törlünk: az adat pár MB, és a törlés visszafordíthatatlan. A napi
-- karbantartásuk már leállt (a workflow-ból kikerült a szótáras címkéző és
-- a Gemini-pótló). Ez a migráció csak MEGJELÖLI őket, hogy egy hónap múlva
-- senki -- se ember, se modell -- ne kezdje el újra használni.
--
-- A `keszseg_valtozat` (11 911 CV-oldali szinonima) NEM ide tartozik: az a
-- CV-felismerés szótára, és az új rendszerben is kell.

comment on table public.keszsegek is
    'BEFAGYASZTVA 2026-07-28. A hirdetésekből kinyert címkék régi láncának '
    'része; a `hirdetes_tetel` váltotta le. Nem frissül, ne épüljön rá új '
    'funkció. Törölni nem törölhető, mert a `keszseg_valtozat` hivatkozik rá.';

comment on table public.hirdetes_keszseg is
    'BEFAGYASZTVA 2026-07-28. A `hirdetes_tetel` váltotta le. Nem frissül, '
    'ne épüljön rá új funkció.';

comment on table public.keszseg_valtozat is
    'ÉL ÉS KELL. A CV-oldali szinonimaszótár: ahogy a felhasználó ÍRJA '
    '(„kasszáztam") vs. a szakmai név („pénztárkezelés"). A `keszsegek` '
    'táblára hivatkozik, de attól függetlenül használjuk.';

comment on table public.hirdetes_tetel is
    'A hirdetések kinyert tételei, szekciók szerint. Ez váltotta le a '
    '`keszsegek`/`hirdetes_keszseg` párost. GENERÁLT: bármikor eldobható és '
    'újraszámolható a hirdetésekből (scripts/hirdetes_tetel_feltolto.py --ujra).';
