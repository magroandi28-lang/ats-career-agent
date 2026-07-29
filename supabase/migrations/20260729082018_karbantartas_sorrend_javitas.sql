-- Utólag mentve az éles migrációs naplóból (20260729082018).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A sorrend számít: előbb látni, aztán lejáratni.
--
-- HIBA VOLT: a pg_cron 05:30-kor futtatta a `napi_karbantartas()`-t, benne a
-- lejáratozással -- a GitHub Action viszont ma 04:00 helyett 06:25-kor
-- indult. Vagyis előbb jelöltünk volna eltűntnek hirdetéseket, mint hogy a
-- söprés megnézte volna, élnek-e. Az ütemező csúszása így adatvesztéssé
-- fordult volna át.
--
-- Két változás:
--   1. A lejáratozás KIKERÜL a napi karbantartásból. Ott a helye, ahol a
--      láttamozás is van: a söprés végén, közvetlenül utána. Így nem lehet
--      rossz sorrendben.
--   2. A karbantartás 08:00 UTC-re csúszik, jóval a gyűjtés mögé, hogy a
--      nézetek a MAI adatból számoljanak, ne a tegnapiból.
create or replace function public.napi_karbantartas()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    cimkezett integer;
begin
    cimkezett := public.tudasanyag_cimkezes();
    perform public.nezetek_frissitese();
    return jsonb_build_object('ujracimkezett_szakasz', cimkezett);
end;
$$;

comment on function public.napi_karbantartas() is
    'Tudasanyag-cimkezes + nezetfrissites. A LEJARATOZAS NEM ITT VAN: az a '
    'sopres vegen fut, közvetlenul a lattamozas utan, kulonben rossz '
    'sorrendben jelolne eltuntnek elo hirdeteseket. pg_cron 08:00 UTC.';

select cron.unschedule('napi-karbantartas');

select cron.schedule(
    'napi-karbantartas',
    '0 8 * * *',
    $$select public.napi_karbantartas()$$
);
