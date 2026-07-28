-- Utólag mentve az éles migrációs naplóból (20260728181553).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

drop materialized view if exists public.mv_ceg_profil;

create materialized view public.mv_ceg_profil as
with allas as (
    select h.ceg_id, h.tartalom_kulcs, h.id, h.cim, h.szakma_id,
           h.ber_min_havi, h.ber_deviza, h.eloszor_latva, h.utoljara_latva
    from public.hirdetesek h
    where h.ceg_id is not null
),
ismetles as (
    select ceg_id, lower(btrim(cim)) as pozicio,
           count(distinct tartalom_kulcs) as alkalom
    from allas group by 1, 2
),
tetel as (
    select a.ceg_id, t.szekcio, t.szoveg
    from allas a join public.hirdetes_tetel t on t.hirdetes_id = a.id
    where t.szekcio in ('ajanlat', 'kultura')
),
alap as (
    select
        c.id as ceg_id,
        c.nev,
        count(distinct a.tartalom_kulcs) as allas_db,
        count(distinct a.szakma_id)      as szakma_db,
        min(a.eloszor_latva)             as elso_hirdetes,
        max(a.utoljara_latva)            as utolso_hirdetes,
        round(percentile_cont(0.5) within group (order by a.ber_min_havi)
              filter (where a.ber_deviza = 'HUF')) as ber_median
    from public.cegek c
    join allas a on a.ceg_id = c.id
    group by c.id, c.nev
)
select
    alap.*,
    case
        when (alap.nev ~* '(munkaer|kölcsönz|kolcsonz|személyzeti|szemelyzeti|recruit|staffing|humán|human resource|közvetít|kozvetit|portál|portal|hiring)')
             or alap.szakma_db > 20
            then 'kozvetito'
        else 'munkaltato'
    end as tipus,
    case when alap.szakma_db > 20 then null
         else (select max(alkalom) from ismetles i where i.ceg_id = alap.ceg_id) end
        as legtobbszor_ujrahirdetve,
    case when alap.szakma_db > 20 then null
         else (select count(*) from ismetles i
                where i.ceg_id = alap.ceg_id and i.alkalom >= 3) end
        as sokszor_ismetelt_pozicio,
    (select array_agg(distinct szoveg) from tetel x
      where x.ceg_id = alap.ceg_id and x.szekcio = 'ajanlat') as igeretek,
    (select array_agg(distinct szoveg) from tetel x
      where x.ceg_id = alap.ceg_id and x.szekcio = 'kultura') as hangnem
from alap;

create unique index mv_ceg_profil_ceg_idx on public.mv_ceg_profil (ceg_id);
create index mv_ceg_profil_allas_idx on public.mv_ceg_profil (allas_db desc);
create index mv_ceg_profil_tipus_idx on public.mv_ceg_profil (tipus);
