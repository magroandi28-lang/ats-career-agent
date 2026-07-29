-- Utólag mentve az éles migrációs naplóból (20260729081825).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A lejáratozás csak akkor fusson, ha a GYŰJTÉS IS FUT.
--
-- SÚLYOS HIBA VOLT, mérve 2026-07-29: a `hirdetes_lejarat` óra alapján
-- jelölt eltűntnek mindent, aminek a `utoljara_latva` mezője 14 napnál
-- régebbi. A mezőt viszont CSAK a söprés frissíti (`hirdetes_lattam`).
-- Ha a söprés nem fut, vagy a láttamozás elhasal, akkor a teljes állomány
-- "eltűnt" lesz, miközben a hirdetések élnek: 15 230 hirdetésből 417 már
-- másnap, a többi két héten belül.
--
-- Óra volt, visszaállítás nem volt.
--
-- A javítás egy halottember-kapcsoló: ha az elmúlt 2 napban EGYETLEN
-- hirdetést sem láttunk (nem volt sikeres gyűjtés), akkor nem járatunk le
-- semmit. Inkább maradjon bent egy betöltött állás, mint hogy egy néma hiba
-- kiürítse az egész piaci képet.
create or replace function public.hirdetes_lejarat(napok integer default 14)
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    darab integer;
    friss integer;
begin
    -- Fut-e egyáltalán a gyűjtés? Ha nem, a lejáratozásnak nincs alapja.
    select count(*) into friss
      from public.hirdetesek
     where utoljara_latva > now() - interval '2 days';

    if friss = 0 then
        raise notice 'Lejaratozas kihagyva: 2 napja nem lattunk egyetlen hirdetest sem.';
        return -1;
    end if;

    update public.hirdetesek
       set allapot = 'eltunt'
     where allapot = 'aktiv'
       and utoljara_latva < now() - make_interval(days => napok);
    get diagnostics darab = row_count;
    return darab;
end;
$$;

comment on function public.hirdetes_lejarat(integer) is
    'Eltuntnek jeloli, amit `napok` napja nem lattunk. HALOTTEMBER-KAPCSOLO: '
    'ha 2 napja egyetlen hirdetest sem lattunk, nem jaratoz le semmit es -1-et '
    'ad vissza -- kulonben egy nema gyujtesi hiba kiuritene a piaci kepet.';

revoke all on function public.hirdetes_lejarat(integer) from public, anon, authenticated;
grant execute on function public.hirdetes_lejarat(integer) to service_role;
