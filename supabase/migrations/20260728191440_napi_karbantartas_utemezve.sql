-- Utólag mentve az éles migrációs naplóból (20260728191440).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A napi karbantartás az ADATBÁZISBAN ütemezve.
--
-- MIÉRT NEM KÍVÜLRŐL: a Supabase REST-végpontja 8 másodpercnél elvágja a
-- lekérdezést. A tudásanyag újracímkézése (2 735 szakasz) és a két
-- materializált nézet újraszámolása ennél tovább tart, tehát a szkriptből
-- hívva CSENDBEN KIMARADT volna. Egy elavult cégprofil vagy bizalmi szint
-- rosszabb, mint a hiánya: a felhasználó nem tudja, hogy régi számot lát.
--
-- Így viszont a gyűjtéstől függetlenül, az adatbázison belül fut le --
-- nincs időkorlát, és akkor is megtörténik, ha a GitHub Action elhasal.
create extension if not exists pg_cron;

-- A gyűjtés 04:00 UTC-kor indul és nagyjából fél óra. A karbantartás 05:30-kor
-- megy, hogy a friss hirdetéseket már beleszámolja.
select cron.schedule(
    'napi-karbantartas',
    '30 5 * * *',
    $$select public.napi_karbantartas()$$
);

comment on function public.napi_karbantartas() is
    'Napi karbantartás: lejáratozás, tudásanyag-címkézés, nézetfrissítés. '
    'pg_cron futtatja 05:30 UTC-kor (napi-karbantartas). NE hívd REST-en '
    'keresztül -- 8 másodpercnél elvágja, és csendben kimarad.';
