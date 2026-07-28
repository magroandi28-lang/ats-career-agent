-- Szakma -> FEOR, hogy a KSH hivatalos keresete végre bekötve legyen.
--
-- MÉRVE, ÉS EZ MEGDÖNTÖTT EGY FELTEVÉST: a FEOR-08 szerkezetileg az ISCO-08-on
-- alapul, de a SZÁMOZÁSA MÁS. Az ESCO "targonca vezetője" ISCO 8344, a FEOR
-- "Targoncavezető" viszont 8425; a "bolti eladó" ESCO 5223, FEOR 5113. A kódon
-- keresztüli összekötés tehát nem működik -- a 193 látszólag egyező négyjegyű
-- kód véletlen egybeesés.
--
-- Névillesztéssel sem szabad: a szóalapú illesztés 22%-ot talált, DE
-- magabiztosan tévedett. "villamosmérnök" -> "Villamosvezető" (a jármű!),
-- "gépészmérnök" -> "Gépésztechnikus", "szociális gondozó" ->
-- "Szociálpolitikus". Egy rossz FEOR rossz FIZETÉST mutatna a felhasználónak,
-- ami rosszabb, mint ha nem mutatunk semmit.
--
-- Ezért csak PONTOS, normalizált névegyezés kerül be. Ez 48 szakma, ami
-- 1 946 valódi állás a 13 567-ből (14,3%). A többihez hivatalos
-- ISCO-FEOR megfeleltetés kell (KSH), vagy tételes emberi átnézés.

create table if not exists public.szakma_feor (
    szakma_id bigint not null
        references public.szakmak(id) on delete cascade,
    feor_kod text not null references public.feor_lista(kod),
    -- 'pontos' : a szakma neve = a FEOR foglalkozás neve, normalizálva
    -- 'hivatalos' : hivatalos ISCO-FEOR megfeleltetésből
    -- 'kezi'   : ember rendelte hozzá, tételesen ellenőrizve
    megbizhatosag text not null
        check (megbizhatosag in ('pontos', 'hivatalos', 'kezi')),
    letrehozva timestamptz not null default now(),
    primary key (szakma_id, feor_kod)
);

create index if not exists szakma_feor_kod_idx on public.szakma_feor (feor_kod);

alter table public.szakma_feor enable row level security;
alter table public.szakma_feor force row level security;
revoke all on table public.szakma_feor from public, anon, authenticated;
grant all on table public.szakma_feor to service_role;

insert into public.szakma_feor (szakma_id, feor_kod, megbizhatosag)
select s.id, f.kod, 'pontos'
from public.szakmak s
join public.feor_lista f
  on public.keszseg_normalizal(f.nev) = public.keszseg_normalizal(s.nev)
on conflict do nothing;

-- A két bérforrás EGYMÁS MELLETT, nem összeolvasztva.
--
-- A hirdetett bér azt mutatja, mit ígérnek MOST; a KSH azt, mit keresnek
-- ténylegesen az ebben a foglalkozásban dolgozók. A kettő nem ugyanaz, és a
-- különbségük önmagában is információ. Ezért nem átlagoljuk össze őket.
create or replace view public.v_szakma_kereset as
select
    s.id   as szakma_id,
    s.nev  as szakma,
    sf.feor_kod,
    f.nev  as feor_nev,
    -- Hirdetett bér: csak forintos, csak értelmezett, duplikátum nélkül.
    (select round(percentile_cont(0.5) within group (order by h.ber_min_havi))
     from public.hirdetesek h
     where h.szakma_id = s.id and h.ber_deviza = 'HUF'
       and h.ber_min_havi is not null)                  as hirdetett_median,
    (select count(distinct h.tartalom_kulcs)
     from public.hirdetesek h
     where h.szakma_id = s.id and h.ber_min_havi is not null) as hirdetett_mintaszam,
    p.ertek                                             as ksh_atlagkereset,
    p.idoszak                                           as ksh_idoszak,
    p.forras                                            as ksh_forras,
    sf.megbizhatosag                                    as megfeleltetes
from public.szakmak s
join public.szakma_feor sf on sf.szakma_id = s.id
join public.feor_lista f   on f.kod = sf.feor_kod
left join public.piaci_statisztikak p
       on p.feor_kod = sf.feor_kod
      and p.mutato = 'brutto_atlagkereset';
