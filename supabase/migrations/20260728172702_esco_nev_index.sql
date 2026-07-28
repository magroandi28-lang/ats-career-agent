-- Az ESCO összes foglalkozásneve egy lapos, indexelt listában.
--
-- A párosítás eddig minden szakmához végigjárta mind a 3 039 foglalkozás
-- alternatív neveit, és mindegyiken meghívta a normalizálót -- így a napi
-- futásban időtúllépésbe futott (`canceling statement due to statement
-- timeout`). Kilapítva egyetlen indexelt egyenlőség-illesztés marad:
-- 1,2 másodperc.
--
-- FRISSÍTENI KELL, ha az ESCO újratöltődik:
--     refresh materialized view public.esco_nev;
create materialized view if not exists public.esco_nev as
select f.uri,
       n.nev,
       public.keszseg_normalizal(n.nev) as normalizalt,
       (n.nev = f.nev) as preferalt
from public.esco_foglalkozas f,
     lateral unnest(array[f.nev] || f.alt_nevek) as n(nev)
where public.keszseg_normalizal(n.nev) <> '';

create index if not exists esco_nev_normalizalt_idx on public.esco_nev (normalizalt);
create index if not exists esco_nev_uri_idx on public.esco_nev (uri);

create or replace function public.szakma_esco_parositas()
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    darab integer;
begin
    -- `distinct on`: ha ugyanaz a szakmanév a preferált ÉS egy alternatív
    -- néven is illeszkedik ugyanarra a foglalkozásra, a preferált nyerjen --
    -- az az erősebb állítás.
    insert into public.szakma_esco (szakma_id, foglalkozas_uri, megbizhatosag)
    select distinct on (s.id, n.uri)
           s.id, n.uri,
           case when n.preferalt then 'pontos' else 'alternativ' end
    from public.szakmak s
    join public.esco_nev n
      on n.normalizalt = public.keszseg_normalizal(s.nev)
    order by s.id, n.uri, n.preferalt desc
    on conflict do nothing;
    get diagnostics darab = row_count;
    return darab;
end;
$$;

revoke all on function public.szakma_esco_parositas() from public, anon, authenticated;
grant execute on function public.szakma_esco_parositas() to service_role;
