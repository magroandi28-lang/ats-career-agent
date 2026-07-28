-- Utólag mentve az éles migrációs naplóból (20260728182551).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Gyűjtőszakmák: amikre nincs EGYETLEN ESCO-foglalkozás, csak egy csoport.
--
-- A "gyári operátor" (353 hirdetés) és a "szállítmányozó" (48) magyar
-- gyűjtőnevek. Az ESCO ~100 konkrét gépkezelőt ismer (pelenkagyártógép-,
-- eloxáló-, fúvógép-kezelő…), de "gyári operátort" nem. Egyiket sem szabad
-- kiválasztani helyette -- az hamis pontosság lenne.
--
-- Helyette az ISCO-CSOPORT a válasz: a "gyári operátor" a 81-82-es
-- főcsoportba tartozik (gépkezelők, összeszerelők). A csoportra vonatkozó
-- mérce a csoport foglalkozásainak KÖZÖS készségeiből áll össze -- ami
-- mindegyikben megvan, az a szakma magja.
create table if not exists public.szakma_isco (
    szakma_id bigint not null references public.szakmak(id) on delete cascade,
    -- ISCO-előtag: '8' főcsoport, '81' alcsoport, '812' csoport…
    isco_elotag text not null check (isco_elotag ~ '^[0-9]{1,4}$'),
    megbizhatosag text not null check (megbizhatosag in ('pontos', 'kezi')),
    letrehozva timestamptz not null default now(),
    primary key (szakma_id, isco_elotag)
);

alter table public.szakma_isco enable row level security;
alter table public.szakma_isco force row level security;
revoke all on table public.szakma_isco from public, anon, authenticated;
grant all on table public.szakma_isco to service_role;

-- A csoportszintű mérce: mely készségek fordulnak elő a csoport
-- foglalkozásainak legalább a felében. Ami ennél ritkább, az egy-egy
-- specializáció sajátja, nem a szakmáé.
create or replace function public.isco_csoport_keszsegei(
    elotag text, min_arany numeric default 0.5
)
returns table (keszseg_uri text, nev text, arany numeric, foglalkozas_db bigint)
language sql
stable
set search_path = public, pg_catalog
as $$
    with csoport as (
        select uri from public.esco_foglalkozas
        where isco_kod like elotag || '%'
    ),
    ossz as (select count(*)::numeric n from csoport)
    select fk.keszseg_uri,
           k.nev,
           round(count(*)::numeric / (select n from ossz), 2) as arany,
           count(*) as foglalkozas_db
    from public.esco_foglalkozas_keszseg fk
    join csoport c on c.uri = fk.foglalkozas_uri
    join public.esco_keszseg k on k.uri = fk.keszseg_uri
    where fk.kotelezo
    group by fk.keszseg_uri, k.nev
    having count(*)::numeric / (select n from ossz) >= min_arany
    order by arany desc, foglalkozas_db desc;
$$;

revoke all on function public.isco_csoport_keszsegei(text, numeric)
    from public, anon, authenticated;
grant execute on function public.isco_csoport_keszsegei(text, numeric) to service_role;

insert into public.szakma_isco (szakma_id, isco_elotag, megbizhatosag)
select s.id, v.elotag, 'kezi'
from public.szakmak s
join (values ('gyári operátor', '81'),
             ('gyári operátor', '82'),
             ('szállítmányozó', '432')) as v(nev, elotag)
  on v.nev = s.nev
on conflict do nothing;
