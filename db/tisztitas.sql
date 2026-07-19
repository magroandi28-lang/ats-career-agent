-- KÉSZSÉG-TISZTÍTÁS ELŐKÉSZÍTÉSE — futtasd a Supabase SQL Editorban
-- 1) Új típus engedélyezése: 'iparag' (pl. "autóipari ismeretek")
alter table public.keszsegek drop constraint if exists keszsegek_tipus_check;
alter table public.keszsegek add constraint keszsegek_tipus_check
    check (tipus in ('elvaras', 'feladat', 'eszkoz', 'soft', 'iparag'));

-- 2) Kanonikus (egységesített) név oszlop
alter table public.keszsegek add column if not exists kanonikus text;

-- 3) A statisztika-nézet mostantól a kanonikus néven csoportosít:
--    a "szoftver tesztelés" és a "szoftvertesztelés" EGY sor lesz.
create or replace view public.v_szakma_keszsegek as
select
    sz.id  as szakma_id,
    sz.nev as szakma,
    coalesce(k.kanonikus, k.nev) as keszseg,
    mode() within group (order by k.tipus) as tipus,
    count(distinct h.id) as elofordulas,
    round(
        100.0 * count(distinct h.id) / nullif(
            (select count(*) from public.hirdetesek h2 where h2.szakma_id = sz.id), 0
        ), 1
    ) as hirdetesek_szazaleka
from public.hirdetesek h
join public.szakmak sz          on sz.id = h.szakma_id
join public.hirdetes_keszseg hk on hk.hirdetes_id = h.id
join public.keszsegek k         on k.id = hk.keszseg_id
group by sz.id, sz.nev, coalesce(k.kanonikus, k.nev)
order by szakma, elofordulas desc;

alter view public.v_szakma_keszsegek set (security_invoker = on);
