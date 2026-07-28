-- Utólag mentve az éles migrációs naplóból (20260728185559).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

drop view if exists public.v_szakma_kereset;

create view public.v_szakma_kereset as
with par as (
    select sf.szakma_id, sf.feor_kod, sf.megbizhatosag, f.nev as feor_nev,
           p.ertek as ksh, p.idoszak, p.forras
    from public.szakma_feor sf
    join public.feor_lista f on f.kod = sf.feor_kod
    left join public.piaci_statisztikak p
           on p.feor_kod = sf.feor_kod and p.mutato = 'brutto_atlagkereset'
),
rang as (
    select *, case megbizhatosag when 'pontos' then 1 when 'kezi' then 2 else 3 end as szint
    from par
),
legjobb as (
    select szakma_id, min(szint) as szint from rang group by szakma_id
),
szurt as (
    select r.* from rang r join legjobb l
      on l.szakma_id = r.szakma_id and l.szint = r.szint
)
select
    s.id as szakma_id,
    s.nev as szakma,
    count(distinct sz.feor_kod)                          as feor_darab,
    min(sz.feor_kod)                                     as feor_kod,
    min(sz.feor_nev)                                     as feor_nev,
    (select round(percentile_cont(0.5) within group (order by h.ber_min_havi))
       from public.hirdetesek h
      where h.szakma_id = s.id and h.ber_deviza = 'HUF'
        and h.ber_min_havi is not null)                  as hirdetett_median,
    (select count(distinct h.tartalom_kulcs)
       from public.hirdetesek h
      where h.szakma_id = s.id and h.ber_min_havi is not null) as hirdetett_mintaszam,
    round(min(sz.ksh))                                   as ksh_min,
    round(max(sz.ksh))                                   as ksh_max,
    case when count(distinct sz.feor_kod) = 1 then round(min(sz.ksh)) end as ksh_atlagkereset,
    min(sz.idoszak)                                      as ksh_idoszak,
    min(sz.forras)                                       as ksh_forras,
    case when count(distinct sz.feor_kod) > 1 then 'bizonytalan'
         else min(sz.megbizhatosag) end                  as megfeleltetes
from public.szakmak s
join szurt sz on sz.szakma_id = s.id
group by s.id, s.nev;

comment on view public.v_szakma_kereset is
    'Szakmánként EGY sor. Ha van pontos névegyezés, az nyer. Ha csak több '
    'hivatalos ISCO-FEOR megfeleltetés van, akkor NEM választunk: sávot adunk '
    '(ksh_min-ksh_max) és megfeleltetes=bizonytalan. Egy sáv igaz; egy '
    'kitalált pontszám nem. A ksh_atlagkereset csak egyértelmű esetben van '
    'kitöltve. FIGYELEM: a KSH-adat 2024-es, a hirdetések 2026-osak.';
