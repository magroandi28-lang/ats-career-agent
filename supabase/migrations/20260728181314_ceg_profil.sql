-- Utólag mentve az éles migrációs naplóból (20260728181314).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Cégprofil a SAJÁT hirdetésekből, külső forrás nélkül.
--
-- A `cegek` tábla 2 122 sorából alig háromnál van leírás, bérsáv vagy
-- fluktuáció -- azok külső lekérdezésre vártak volna. Közben a saját
-- adatunkban ott van mindaz, amit egy jelentkező tudni akar, mielőtt belép:
--
--   mit ígér a cég       -> az `ajanlat` szekció tételei
--   hogyan beszél magáról -> a `kultura` szekció tételei
--   mennyit fizet         -> a hirdetett bér mediánja
--   mennyire pörög        -> UGYANAZT a pozíciót hányszor hirdette újra
--
-- Az utolsó a fluktuáció közelítése, és ez a legértékesebb: ha egy cég
-- ugyanarra a munkakörre hónapokon belül újra és újra hirdet, az jelzés.
-- Nem vélemény, nem pletyka -- a saját hirdetéseiből számolva, idézhetően.
create materialized view if not exists public.mv_ceg_profil as
with allas as (
    select h.ceg_id, h.tartalom_kulcs, h.id, h.cim, h.szakma_id,
           h.ber_min_havi, h.ber_deviza, h.eloszor_latva, h.utoljara_latva
    from public.hirdetesek h
    where h.ceg_id is not null
),
ismetles as (
    -- Ugyanaz a pozíció ugyanannál a cégnél, több KÜLÖNBÖZŐ hirdetésként.
    select ceg_id, lower(btrim(cim)) as pozicio,
           count(distinct tartalom_kulcs) as alkalom
    from allas group by 1, 2
),
tetel as (
    select a.ceg_id, t.szekcio, t.szoveg
    from allas a join public.hirdetes_tetel t on t.hirdetes_id = a.id
    where t.szekcio in ('ajanlat', 'kultura')
)
select
    c.id as ceg_id,
    c.nev,
    count(distinct a.tartalom_kulcs)                      as allas_db,
    count(distinct a.szakma_id)                           as szakma_db,
    min(a.eloszor_latva)                                  as elso_hirdetes,
    max(a.utoljara_latva)                                 as utolso_hirdetes,
    round(percentile_cont(0.5) within group (order by a.ber_min_havi)
          filter (where a.ber_deviza = 'HUF'))            as ber_median,
    (select max(alkalom) from ismetles i where i.ceg_id = c.id)      as legtobbszor_ujrahirdetve,
    (select count(*) from ismetles i where i.ceg_id = c.id and i.alkalom >= 3) as sokszor_ismetelt_pozicio,
    (select array_agg(distinct szoveg) from tetel x
      where x.ceg_id = c.id and x.szekcio = 'ajanlat')    as igeretek,
    (select array_agg(distinct szoveg) from tetel x
      where x.ceg_id = c.id and x.szekcio = 'kultura')    as hangnem
from public.cegek c
join allas a on a.ceg_id = c.id
group by c.id, c.nev;

create unique index if not exists mv_ceg_profil_ceg_idx on public.mv_ceg_profil (ceg_id);
create index if not exists mv_ceg_profil_allas_idx on public.mv_ceg_profil (allas_db desc);
