-- Utólag mentve az éles migrációs naplóból (20260728183253).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A migrációk kiolvasása, hogy a repo és az adatbázis ne csússzon szét.
--
-- Ma reggel derült ki, hogy a kettő már elcsúszott: a DB naplója 7
-- bejegyzést ismert, a repóban 9 fájl volt, a metszet 4. Az ok, hogy DDL
-- ment be kézzel, SQL-szerkesztőből -- és így az adatbázis NEM ÉPÍTHETŐ
-- ÚJRA a repóból.
--
-- Ez a függvény kiolvashatóvá teszi a naplót, hogy a
-- scripts/migracio_szinkron.py bármikor pótolni tudja a hiányzó fájlokat.
-- A megelőzés ettől még fontosabb: DDL csak migrációval mehet.
create or replace function public.migraciok()
returns table (version text, name text, sql text)
language sql
stable
security definer
set search_path = supabase_migrations, pg_catalog
as $$
    select m.version, m.name, array_to_string(m.statements, E';\n\n')
    from supabase_migrations.schema_migrations m
    order by m.version;
$$;

revoke all on function public.migraciok() from public, anon, authenticated;
grant execute on function public.migraciok() to service_role;
