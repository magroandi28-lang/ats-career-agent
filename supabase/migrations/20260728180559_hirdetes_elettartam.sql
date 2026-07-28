-- Utólag mentve az éles migrációs naplóból (20260728180559).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Meddig él egy hirdetés.
--
-- Eddig csak `letrehozva` volt: egy hirdetés sosem járt le. Ma ez nem
-- látszik (két hét adat), de fél év múlva a piaci körkép többségében
-- betöltött állásokból számolna, és nem lenne mód megkülönböztetni.
--
-- A historikus adat MEGMARAD -- abból lesz a trend ("ebben a szakmában
-- három hónap alatt 40%-kal nőtt a hirdetésszám"). Csak a piaci nézetek
-- szűrnek aktívra.

alter table public.hirdetesek
    add column if not exists eloszor_latva timestamptz,
    add column if not exists utoljara_latva timestamptz,
    add column if not exists allapot text not null default 'aktiv';

-- A meglévő soroknál a gyűjtés ideje az egyetlen, amit tudunk.
update public.hirdetesek
   set eloszor_latva = coalesce(eloszor_latva, letrehozva),
       utoljara_latva = coalesce(utoljara_latva, letrehozva)
 where eloszor_latva is null or utoljara_latva is null;

alter table public.hirdetesek
    alter column eloszor_latva set default now(),
    alter column utoljara_latva set default now();

alter table public.hirdetesek
    drop constraint if exists hirdetesek_allapot_check;
alter table public.hirdetesek
    add constraint hirdetesek_allapot_check
        check (allapot in ('aktiv', 'eltunt', 'lejart'));

create index if not exists hirdetesek_allapot_idx
    on public.hirdetesek (allapot, szakma_id);

-- A gyűjtő ezzel jelzi, hogy egy linket MOST is látott. Nem ír új sort,
-- csak frissíti a láttamozást -- így derül ki, mi tűnt el a piacról.
create or replace function public.hirdetes_lattam(linkek text[])
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    darab integer;
begin
    update public.hirdetesek
       set utoljara_latva = now(),
           allapot = 'aktiv'
     where link = any(linkek);
    get diagnostics darab = row_count;
    return darab;
end;
$$;

-- Ami 14 napja nem jött vissza egyetlen söprésben sem, az eltűnt a piacról.
-- Két hét azért kell, mert a Jooble lekérdezésenkénti 600-as korlátja miatt
-- egy hirdetés kimaradhat egy-egy futásból anélkül, hogy megszűnt volna.
create or replace function public.hirdetes_lejarat(napok integer default 14)
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    darab integer;
begin
    update public.hirdetesek
       set allapot = 'eltunt'
     where allapot = 'aktiv'
       and utoljara_latva < now() - make_interval(days => napok);
    get diagnostics darab = row_count;
    return darab;
end;
$$;

revoke all on function public.hirdetes_lattam(text[]) from public, anon, authenticated;
revoke all on function public.hirdetes_lejarat(integer) from public, anon, authenticated;
grant execute on function public.hirdetes_lattam(text[]) to service_role;
grant execute on function public.hirdetes_lejarat(integer) to service_role;
