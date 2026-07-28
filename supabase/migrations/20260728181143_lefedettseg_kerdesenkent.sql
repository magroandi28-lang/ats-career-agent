-- Utólag mentve az éles migrációs naplóból (20260728181143).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Kérdésenkénti bizalom, nem egyetlen jelző.
--
-- Az első változat egyetlen `bizalom` mezőt adott, és a legszigorúbb
-- kérdéshez igazította az összeset: 555 szakmából 472 lett "nincs". Ez
-- félrevezető volt. A kérdések ugyanis különböző mennyiségű adatot
-- igényelnek:
--
--   "Van-e kereslet?"     -> néhány hirdetés is elég, a puszta létezés a válasz
--   "Mennyit fizetnek?"   -> legalább 10 értelmezett béradat kell a mediánhoz
--   "Mit várnak el?"      -> csak sok kinyert tételből áll össze
--
-- Így egy szakmáról lehet őszintén annyit mondani, hogy "van rá kereslet,
-- de a bérről nincs elég adatom" -- ami igaz, hasznos, és nem hallgatás.
drop materialized view if exists public.mv_szakma_lefedettseg;

create materialized view public.mv_szakma_lefedettseg as
select
    s.id  as szakma_id,
    s.nev as szakma,
    count(distinct h.tartalom_kulcs) filter (where h.allapot = 'aktiv') as allas,
    count(distinct h.ceg_id)         filter (where h.allapot = 'aktiv') as ceg,
    count(distinct h.tartalom_kulcs) filter (where h.ber_min_havi is not null
                                               and h.ber_deviza = 'HUF')  as beres,
    count(distinct t.hirdetes_id) filter (where t.szekcio in ('elvaras','feladat')) as teteles,
    exists (select 1 from public.szakma_esco e where e.szakma_id = s.id) as van_esco,
    exists (select 1 from public.szakma_feor f where f.szakma_id = s.id) as van_ksh,
    max(h.utoljara_latva) as legfrissebb,

    -- Van-e kereslet: ehhez kevés is elég, mert a kérdés maga kevés.
    case when count(distinct h.tartalom_kulcs) filter (where h.allapot='aktiv') >= 20 then 'eros'
         when count(distinct h.tartalom_kulcs) filter (where h.allapot='aktiv') >= 5  then 'gyenge'
         else 'nincs' end as kereslet_bizalom,

    -- Bér: 10 adat alatt a medián egyetlen szélsőségtől elmozdul.
    case when count(distinct h.tartalom_kulcs) filter (where h.ber_min_havi is not null
                                                         and h.ber_deviza='HUF') >= 10 then 'eros'
         when count(distinct h.tartalom_kulcs) filter (where h.ber_min_havi is not null
                                                         and h.ber_deviza='HUF') >= 4  then 'gyenge'
         else 'nincs' end as ber_bizalom,

    -- Elvárások: itt kell a legtöbb, mert kifejezés-gyakoriságot számolunk.
    case when count(distinct t.hirdetes_id) filter (where t.szekcio in ('elvaras','feladat')) >= 30 then 'eros'
         when count(distinct t.hirdetes_id) filter (where t.szekcio in ('elvaras','feladat')) >= 10 then 'gyenge'
         else 'nincs' end as elvaras_bizalom
from public.szakmak s
left join public.hirdetesek h    on h.szakma_id = s.id
left join public.hirdetes_tetel t on t.hirdetes_id = h.id
group by s.id, s.nev;

create unique index mv_szakma_lefedettseg_szakma_idx
    on public.mv_szakma_lefedettseg (szakma_id);
create index mv_szakma_lefedettseg_kereslet_idx
    on public.mv_szakma_lefedettseg (kereslet_bizalom);
