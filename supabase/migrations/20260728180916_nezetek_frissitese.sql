-- Utólag mentve az éles migrációs naplóból (20260728180916).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A számolt nézetek frissítése egyetlen hívással.
--
-- A napi gyűjtés végén kell futnia, különben a lefedettségi kapu és az
-- átjárhatóság egy napot késne a valósághoz képest.
--
-- Az `esco_nev` és az `esco_szomszed` csak akkor változik, ha az ESCO
-- újratöltődik -- azok ritkán, kézzel frissülnek. A lefedettség viszont
-- minden gyűjtés után más.
create or replace function public.nezetek_frissitese()
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
    refresh materialized view concurrently public.mv_szakma_lefedettseg;
end;
$$;

revoke all on function public.nezetek_frissitese() from public, anon, authenticated;
grant execute on function public.nezetek_frissitese() to service_role;
