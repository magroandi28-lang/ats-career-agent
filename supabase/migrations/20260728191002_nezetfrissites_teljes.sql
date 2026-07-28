-- Utólag mentve az éles migrációs naplóból (20260728191002).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A napi frissítés MINDEN számolt nézetre kiterjed.
--
-- Az első változat csak a lefedettséget frissítette. A cégprofil így egy hét
-- alatt elavult volna: új hirdetések jönnek, a cég ígéretei és a
-- pozíció-ismétlődés viszont a régi számokat mutatná. Egy elavult
-- fluktuáció-jelzés rosszabb, mint a hiánya.
--
-- Az `esco_nev` és az `esco_szomszed` szándékosan marad ki: azok csak akkor
-- változnak, ha az ESCO-t újratöltjük -- az kézi, ritka művelet, és a
-- betöltő kiírja, hogy frissíteni kell.
create or replace function public.nezetek_frissitese()
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
    refresh materialized view concurrently public.mv_szakma_lefedettseg;
    refresh materialized view concurrently public.mv_ceg_profil;
end;
$$;

revoke all on function public.nezetek_frissitese() from public, anon, authenticated;
grant execute on function public.nezetek_frissitese() to service_role;

-- A tudásanyag címkézése is fusson naponta: ha új szakasz kerül be
-- (tudasbazis_feltolto), az címke nélkül maradna, és a témára szűrt keresés
-- nem találná meg.
create or replace function public.napi_karbantartas()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    lejart integer;
    cimkezett integer;
begin
    lejart := public.hirdetes_lejarat(14);
    cimkezett := public.tudasanyag_cimkezes();
    perform public.nezetek_frissitese();
    return jsonb_build_object(
        'eltuntnek_jelolve', lejart,
        'ujracimkezett_szakasz', cimkezett);
end;
$$;

revoke all on function public.napi_karbantartas() from public, anon, authenticated;
grant execute on function public.napi_karbantartas() to service_role;
