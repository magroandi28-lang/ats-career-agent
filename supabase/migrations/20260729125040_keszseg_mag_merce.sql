-- A negyedik adatőr-mérce: mennyire tiszta egy szakma készséglistája.
--
-- MIÉRT KELL: a besorolásra, a frissességre és a bérre már van napi mércénk,
-- az ESCO-készségrétegre nem volt. Ezért maradhatott észrevétlen, hogy egy
-- általános raktáros emlékeztetőjének eleje bőripari készség volt -- kézzel
-- kellett megtalálni.
--
-- Amit mér: a szakma készségeinek hány százaléka tartozik a MAGHOZ (a
-- szakma foglalkozásainak legalább negyedénél szerepel). Ha ez lezuhan, a
-- lista zajossá vált, és a CV-emlékeztető félrevezetne.
--
-- Egyetlen hívás az egész adatbázisra: az adatőr nem futtathat 987 külön
-- lekérdezést naponta.
create or replace function public.keszseg_mag_merce(p_kuszob numeric default 0.25)
returns table (szakma_id bigint, szakma text, ossz_keszseg integer,
               mag_keszseg integer, mag_szazalek numeric)
language sql
stable
set search_path to 'public', 'pg_catalog'
as $$
with foglalkozas_db as (
    select szakma_id, greatest(count(*), 1)::numeric as db
    from public.szakma_esco group by szakma_id
),
keszseg as (
    select se.szakma_id, fk.keszseg_uri,
           count(distinct se.foglalkozas_uri)::numeric as foglalkozas_szam
    from public.szakma_esco se
    join public.esco_foglalkozas_keszseg fk
      on fk.foglalkozas_uri = se.foglalkozas_uri
    group by se.szakma_id, fk.keszseg_uri
)
select s.id, s.nev,
       count(*)::integer as ossz_keszseg,
       count(*) filter (
           where k.foglalkozas_szam / f.db >= p_kuszob)::integer as mag_keszseg,
       round(100.0 * count(*) filter (
           where k.foglalkozas_szam / f.db >= p_kuszob) / count(*), 1)
           as mag_szazalek
from keszseg k
join foglalkozas_db f on f.szakma_id = k.szakma_id
join public.szakmak s on s.id = k.szakma_id
group by s.id, s.nev;
$$;

revoke all on function public.keszseg_mag_merce(numeric)
    from public, anon, authenticated;
grant execute on function public.keszseg_mag_merce(numeric) to service_role;

comment on function public.keszseg_mag_merce(numeric) is
    'Adator-merce: szakmankent a keszseglista maganak aranya. Ha lezuhan, a '
    'CV-emlekezteto zajossa valt.';