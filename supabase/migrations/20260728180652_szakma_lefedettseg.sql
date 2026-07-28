-- Utólag mentve az éles migrációs naplóból (20260728180652).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Mikor szabad a rendszernek állítania valamit, és mikor kell hallgatnia.
--
-- A hitelesség nem attól van, hogy mindenre van válasz, hanem hogy a
-- rendszer meg meri mondani: erre a szakmára nincs elég adatom. Ma 555
-- szakma van, és a hirdetésszámuk nagyon szórt -- van, amelyikre egyetlen
-- hirdetés jut. Ugyanolyan magabiztosan nyilatkozni mindkettőről hazugság.
--
-- A `bizalom` mező megy bele a modell promptjába is: 'nincs' esetén a
-- rendszer nem állít piaci tényt, legfeljebb az ESCO-ból mondja el, MI ez
-- a szakma -- de azt nem, hogy mennyit ér.
create materialized view if not exists public.mv_szakma_lefedettseg as
select
    s.id  as szakma_id,
    s.nev as szakma,
    count(distinct h.tartalom_kulcs) filter (where h.allapot = 'aktiv') as allas,
    count(distinct h.ceg_id)         filter (where h.allapot = 'aktiv') as ceg,
    count(distinct t.hirdetes_id) filter (where t.szekcio = 'elvaras')  as elvarasos,
    count(distinct t.hirdetes_id) filter (where t.szekcio = 'feladat')  as feladatos,
    count(distinct h.id) filter (where h.ber_min_havi is not null)      as beres,
    exists (select 1 from public.szakma_esco e where e.szakma_id = s.id) as van_esco,
    exists (select 1 from public.szakma_feor f where f.szakma_id = s.id) as van_ksh,
    max(h.utoljara_latva) as legfrissebb,
    case
        when count(distinct h.tartalom_kulcs) filter (where h.allapot = 'aktiv') >= 100
         and count(distinct t.hirdetes_id) filter (where t.szekcio in ('elvaras','feladat')) >= 30
            then 'eros'
        when count(distinct h.tartalom_kulcs) filter (where h.allapot = 'aktiv') >= 30
            then 'gyenge'
        else 'nincs'
    end as bizalom
from public.szakmak s
left join public.hirdetesek h    on h.szakma_id = s.id
left join public.hirdetes_tetel t on t.hirdetes_id = h.id
group by s.id, s.nev;

create unique index if not exists mv_szakma_lefedettseg_szakma_idx
    on public.mv_szakma_lefedettseg (szakma_id);
create index if not exists mv_szakma_lefedettseg_bizalom_idx
    on public.mv_szakma_lefedettseg (bizalom);
