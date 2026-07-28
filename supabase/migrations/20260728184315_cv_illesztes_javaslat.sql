-- Utólag mentve az éles migrációs naplóból (20260728184315).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- MÉRVE 2026-07-28: a CV és az ESCO-készségnevek SZIGORÚ szóillesztése
-- nulla találatot adott. A "targoncát vezettem a raktárban" és a "villás
-- targoncát működtet" ugyanaz a munka, de csak egy szavuk közös.
--
-- Ezért a függvény NEM ÁLLÍT, hanem JAVASOL: megmondja, hány jelentéses szó
-- közös, és a hívó dönt. Egy közös szó gyenge jel, három erős. A `megvan`
-- mező eltűnt -- helyette `egyezo_szo` van, ami szám, nem ítélet.
--
-- Ez illeszkedik ahhoz, amire az ESCO a CV-nél valóban jó (és amire nem):
--   JÓ:  szókincs ("ezt így hívják szakmailag") és emlékeztető
--        ("ezt is csináltad?") -- ehhez nem kell automatikus illesztés,
--        elég a lista, amit a felhasználó végignéz.
--   NEM: megpontozni a CV-t. Az ATS a hirdetéshez mér, nem az ESCO-hoz.
drop function if exists public.cv_illesztes(bigint, text[]);

create or replace function public.cv_illesztes(
    p_szakma_id bigint,
    p_cv_kifejezesek text[] default '{}'
)
returns table (
    keszseg_uri text,
    keszseg text,
    kotelezo boolean,
    egyezo_szo integer,
    cv_bizonyitek text
)
language sql
stable
set search_path = public, pg_catalog
as $$
with keszseg as (
    select distinct k.uri, k.nev, fk.kotelezo
    from public.szakma_esco se
    join public.esco_foglalkozas_keszseg fk on fk.foglalkozas_uri = se.foglalkozas_uri
    join public.esco_keszseg k on k.uri = fk.keszseg_uri
    where se.szakma_id = p_szakma_id
),
cv as (
    select kif,
           array(select w from unnest(
                    string_to_array(public.keszseg_normalizal(kif), ' ')) w
                  where length(w) >= 5) as szavak
    from unnest(coalesce(p_cv_kifejezesek, '{}')) kif
),
ks as (
    select uri, nev, kotelezo,
           array(select w from unnest(
                    string_to_array(public.keszseg_normalizal(nev), ' ')) w
                  where length(w) >= 5) as szavak
    from keszseg
),
parok as (
    select ks.uri, cv.kif,
           (select count(*) from unnest(ks.szavak) kw
             where exists (select 1 from unnest(cv.szavak) cw
                            where cw like left(kw, 5) || '%'
                               or kw like left(cw, 5) || '%')) as egyezes
    from ks cross join cv
    where cardinality(ks.szavak) > 0 and cardinality(cv.szavak) > 0
),
legjobb as (
    select distinct on (uri) uri, kif, egyezes
    from parok where egyezes > 0
    order by uri, egyezes desc, length(kif)
)
select ks.uri, ks.nev, ks.kotelezo,
       coalesce(l.egyezes, 0)::integer as egyezo_szo,
       l.kif as cv_bizonyitek
from ks
left join legjobb l on l.uri = ks.uri
order by coalesce(l.egyezes, 0) desc, ks.kotelezo desc, ks.nev;
$$;

revoke all on function public.cv_illesztes(bigint, text[]) from public, anon, authenticated;
grant execute on function public.cv_illesztes(bigint, text[]) to service_role;
