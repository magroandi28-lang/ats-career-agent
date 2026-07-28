-- Az új szakmák bekötése az ESCO-hoz, egyetlen hívással.
--
-- A söprés minden nap talál olyan szakmát, ami eddig nem volt. Ezek pontosan
-- az ESCO preferált nevéről kapják a nevüket, tehát a normalizált névegyezés
-- gyakorlatilag mindet megtalálja -- 2026-07-28-án 714-ből 712-t.
--
-- Azért függvény és nem szkript: a névnormalizálás (`keszseg_normalizal`) az
-- adatbázisban él, és így a feltöltő és a párosítás biztosan ugyanazt számolja.
--
-- FIGYELEM: ezt a változatot a következő migráció (esco_nev_index) lecseréli,
-- mert így időtúllépésbe futott -- minden szakmához végigjárta mind a 3 039
-- foglalkozás alternatív neveit. A fájl a napló hűsége miatt marad meg.
create or replace function public.szakma_esco_parositas()
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    uj integer := 0;
    darab integer;
begin
    insert into public.szakma_esco (szakma_id, foglalkozas_uri, megbizhatosag)
    select s.id, f.uri, 'pontos'
    from public.szakmak s
    join public.esco_foglalkozas f
      on f.normalizalt = public.keszseg_normalizal(s.nev)
    on conflict do nothing;
    get diagnostics darab = row_count;
    uj := uj + darab;

    insert into public.szakma_esco (szakma_id, foglalkozas_uri, megbizhatosag)
    select s.id, f.uri, 'alternativ'
    from public.szakmak s
    join public.esco_foglalkozas f
      on exists (select 1 from unnest(f.alt_nevek) a
                 where public.keszseg_normalizal(a) = public.keszseg_normalizal(s.nev))
    on conflict do nothing;
    get diagnostics darab = row_count;
    uj := uj + darab;

    return uj;
end;
$$;

revoke all on function public.szakma_esco_parositas() from public, anon, authenticated;
grant execute on function public.szakma_esco_parositas() to service_role;
