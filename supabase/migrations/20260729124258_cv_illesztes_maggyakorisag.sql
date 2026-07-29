-- A készségek a szakma MAGJA szerint rangsorolódjanak, ne uniózva.
--
-- HIBA VOLT: a `keszseg` CTE `distinct`-tel összeöntötte a szakmához kötött
-- ÖSSZES ESCO-foglalkozás készséglistáját. A „raktáros" hat foglalkozáshoz
-- kötődik -- raktáros, raktárgazdálkodó, nyersanyagraktáros, bőrgyári
-- raktáros, cipőgyári raktáros, ruhaipari raktáros --, mind valóban raktáros,
-- de a bőrgyárié olyan iparági tudást hoz magával, mint „a kéregbőr
-- fizikai-kémiai tulajdonságai". Mérve 2026-07-29: egy általános raktáros
-- 118 tételes emlékeztetőjének eleje bőripari készség volt.
--
-- A JAVÍTÁS: megszámoljuk, egy készség a szakma hány foglalkozásánál
-- szerepel. Ami hatból hatnál, az a szakma magja. Ami hatból egynél, az
-- iparági különlegesség. A `mag_arany` ezt adja 0 és 1 között.
--
-- Nem dobjuk el a ritka készségeket -- egy bőrgyári raktárosnak azok a
-- helyesek --, csak a sorrend végére kerülnek, és a hívó szűrhet rájuk a
-- `p_min_mag` küszöbbel.

drop function if exists public.cv_illesztes(bigint, text[]);

create or replace function public.cv_illesztes(
    p_szakma_id bigint,
    p_cv_kifejezesek text[] default '{}',
    p_min_mag numeric default 0
)
returns table (
    keszseg_uri text,
    keszseg text,
    kotelezo boolean,
    foglalkozas_szam integer,
    mag_arany numeric,
    egyezo_szo integer,
    cv_bizonyitek text
)
language sql
stable
set search_path to 'public', 'pg_catalog'
as $function$
with foglalkozas_db as (
    select greatest(count(*), 1)::numeric as db
    from public.szakma_esco where szakma_id = p_szakma_id
),
keszseg as (
    select k.uri, k.nev,
           bool_or(fk.kotelezo) as kotelezo,
           count(distinct se.foglalkozas_uri)::integer as foglalkozas_szam
    from public.szakma_esco se
    join public.esco_foglalkozas_keszseg fk
      on fk.foglalkozas_uri = se.foglalkozas_uri
    join public.esco_keszseg k on k.uri = fk.keszseg_uri
    where se.szakma_id = p_szakma_id
    group by k.uri, k.nev
),
cv as (
    select kif,
           array(select w from unnest(
                    string_to_array(public.keszseg_normalizal(kif), ' ')) w
                  where length(w) >= 5) as szavak
    from unnest(coalesce(p_cv_kifejezesek, '{}')) kif
),
ks as (
    select uri, nev, kotelezo, foglalkozas_szam,
           round(foglalkozas_szam / (select db from foglalkozas_db), 3)
               as mag_arany,
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
select ks.uri, ks.nev, ks.kotelezo, ks.foglalkozas_szam, ks.mag_arany,
       coalesce(l.egyezes, 0)::integer as egyezo_szo,
       l.kif as cv_bizonyitek
from ks
left join legjobb l on l.uri = ks.uri
where ks.mag_arany >= coalesce(p_min_mag, 0)
-- A CV-ben igazolt készség jön elöl, utána a szakma magja. Egy iparági
-- különlegesség sosem előzhet meg egy olyat, amit a szakma minden
-- foglalkozásánál elvárnak.
order by coalesce(l.egyezes, 0) desc, ks.mag_arany desc,
         ks.kotelezo desc, ks.nev;
$function$;

revoke all on function public.cv_illesztes(bigint, text[], numeric)
    from public, anon, authenticated;
grant execute on function public.cv_illesztes(bigint, text[], numeric)
    to service_role;

comment on function public.cv_illesztes(bigint, text[], numeric) is
    'A szakma ESCO-keszsegei, maggyakorisag szerint rangsorolva. A mag_arany '
    'megmondja, a szakma hany foglalkozasanal szerepel a keszseg (0-1). '
    'A p_min_mag kuszobbel az iparagi kulonlegessegek kiszurhetok.';