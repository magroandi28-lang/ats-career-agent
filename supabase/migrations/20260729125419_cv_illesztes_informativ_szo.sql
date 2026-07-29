-- Az általános igék ne számítsanak bizonyítéknak.
--
-- HIBA VOLT: a „Targoncát vezettem" mondat illeszkedett „a gyártás során
-- leltárt VEZET a termékekről" készségre, mert a két szövegben közös a
-- „vezet" szótő. Egyetlen általános ige egyezése bizonyítéknak számított.
--
-- MIÉRT NEM KÉZI TILTÓLISTA: azt karban kellene tartani, és mindig lemaradna
-- valami. Ehelyett MÉRJÜK, mely szótövek általánosak. Mérve 2026-07-29:
-- „kezel" 589 készségnévben szerepel, „vegez" 512, „haszn" 398 -- ezek nem
-- különböztetnek meg semmit. Egy 13 939 elemű készségtárban az a szótő
-- informatív, ami keveset fog meg.
create materialized view if not exists public.esco_keszseg_szoto as
with szavak as (
    select left(w, 5) as szoto, k.uri
    from public.esco_keszseg k,
         unnest(string_to_array(public.keszseg_normalizal(k.nev), ' ')) w
    where length(w) >= 5
)
select szoto, count(distinct uri)::integer as keszseg_db
from szavak group by szoto;

create unique index if not exists esco_keszseg_szoto_idx
    on public.esco_keszseg_szoto (szoto);

revoke all on table public.esco_keszseg_szoto from public, anon, authenticated;
grant select on table public.esco_keszseg_szoto to service_role;

comment on materialized view public.esco_keszseg_szoto is
    'Szotő -> hany ESCO-keszsegnevben szerepel. A cv_illesztes ebbol donti '
    'el, mi szamit bizonyiteknak. Csak ESCO-import utan kell frissiteni.';


-- Az illesztés mostantól INFORMATÍV szótövet követel.
create or replace function public.cv_illesztes(
    p_szakma_id bigint,
    p_cv_kifejezesek text[] default '{}',
    p_min_mag numeric default 0,
    p_szo_kuszob integer default 100
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
           -- CSAK az informatív szavak maradnak. Ami tobb szaz keszsegnevben
           -- szerepel, az nem mond semmit arrol, hogy ez a keszseg-e.
           array(select w from unnest(
                    string_to_array(public.keszseg_normalizal(nev), ' ')) w
                  where length(w) >= 5
                    and coalesce((select sz.keszseg_db
                                    from public.esco_keszseg_szoto sz
                                   where sz.szoto = left(w, 5)), 0)
                        < p_szo_kuszob) as szavak
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
order by coalesce(l.egyezes, 0) desc, ks.mag_arany desc,
         ks.kotelezo desc, ks.nev;
$function$;

revoke all on function public.cv_illesztes(bigint, text[], numeric, integer)
    from public, anon, authenticated;
grant execute on function public.cv_illesztes(bigint, text[], numeric, integer)
    to service_role;