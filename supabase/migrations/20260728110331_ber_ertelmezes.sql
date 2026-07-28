-- A hirdetett bér szövegből számmá.
--
-- Eddig a `bersav` szöveg volt ("400 000 Ft/hó", "2 500 Ft/óra",
-- "2 800 - 3 000 €/hó"), és 9 630 sorban ÜRES STRING, nem NULL -- ezért a
-- `bersav is not null` szűrő 11 701 találatot adott, pedig csak ~2 000-ben
-- volt tényleges bér. Így nem lehetett mediánt számolni és nem lehetett a
-- KSH-adathoz mérni.
--
-- Nulla modellhívás, mindig ugyanaz az eredmény.
--
-- MEGJEGYZÉS: ez a migráció 20260728110331 néven már lefutott az éles
-- adatbázison; ez a fájl utólag készült róla, hogy a repo és az adatbázis
-- ne csússzon el egymástól (lásd a séma-elcsúszásról szóló feladatot).

create table if not exists public.arfolyam (
    deviza    text primary key,
    huf       numeric not null check (huf > 0),
    ervenyes  date not null,
    forras    text not null
);
comment on table public.arfolyam is
    'Devizaárfolyam a béradatok forintosításához. Amelyik devizára nincs sor, '
    'az kimarad a forintos statisztikákból -- inkább hiányzik, mint hazudik.';

insert into public.arfolyam (deviza, huf, ervenyes, forras)
values ('HUF', 1, current_date, 'azonossag')
on conflict (deviza) do nothing;

-- Óra -> hó: 174 óra a teljes munkaidős magyar havi óraszám (40 óra/hét).
-- Nap -> hó: 21.75 munkanap. Ez a két szám vitatható, ezért van EGY helyen.
create or replace function public.ber_ertelmez(szoveg text)
returns jsonb
language sql
immutable
set search_path = pg_catalog, public
as $$
with nyers as (
    select regexp_replace(
             regexp_replace(replace(coalesce(szoveg, ''), chr(160), ' '),
                            '(\d)\s+(?=\d)', '\1', 'g'),
             '\s+', ' ', 'g') as t
),
alap as (
    select t,
        case when t ~* '€|eur'         then 'EUR'
             when t ~* 'ft|huf|forint' then 'HUF'
        end as deviza,
        -- Az óra ellenőrzése áll elöl: a "Ft/óra" a "hó"-ra is illeszkedne.
        case when t ~* 'óra|ora'       then 'ora'
             when t ~* 'hó|hónap'      then 'ho'
             when t ~* 'nap'           then 'nap'
             when t ~* 'év'            then 'ev'
        end as egyseg
    from nyers
),
szamok as (
    select alap.*,
        (regexp_match(t, '(\d+)\s*[-–]\s*(\d+)'))[1]::numeric as tol,
        (regexp_match(t, '(\d+)\s*[-–]\s*(\d+)'))[2]::numeric as ig,
        (regexp_match(t, '(\d+)'))[1]::numeric                as egy
    from alap
),
hatarok as (
    select deviza, egyseg,
        coalesce(tol, egy) as bmin,
        coalesce(ig,  egy) as bmax,
        -- Épeszűségi határok. A gyűjtött adatban van "1 - 1 000 000 Ft/hó":
        -- az alsó határ nyilvánvalóan hibás, és egy ilyen sor elrontaná a
        -- mediánt. Ha BÁRMELYIK határ képtelen, az egész sor értelmezhetetlen.
        case egyseg || '/' || coalesce(deviza, '?')
            when 'ho/HUF'  then array[80000, 8000000]
            when 'ora/HUF' then array[800, 30000]
            when 'nap/HUF' then array[5000, 300000]
            when 'ev/HUF'  then array[1000000, 100000000]
            when 'ho/EUR'  then array[400, 30000]
            when 'ora/EUR' then array[3, 300]
            when 'nap/EUR' then array[20, 3000]
            when 'ev/EUR'  then array[5000, 400000]
        end as sav,
        case egyseg when 'ora' then 174 when 'nap' then 21.75
                    when 'ev' then 1.0/12 else 1 end as havi_szorzo
    from szamok
)
select case
    when deviza is null or egyseg is null or bmin is null or sav is null
        then jsonb_build_object('ok', false, 'ok_nem', 'nem_ertelmezheto')
    when bmin < sav[1] or bmax > sav[2] or bmax < bmin
        then jsonb_build_object('ok', false, 'ok_nem', 'keptelen_ertek')
    else jsonb_build_object(
        'ok',        true,
        'deviza',    deviza,
        'egyseg',    egyseg,
        'min',       bmin,
        'max',       bmax,
        'min_havi',  round(bmin * havi_szorzo),
        'max_havi',  round(bmax * havi_szorzo))
end
from hatarok
$$;

-- Generált oszlop: soha nem csúszhat el a nyers szövegtől, mert a Postgres
-- számolja újra minden íráskor.
alter table public.hirdetesek
    add column if not exists ber_deviza text
        generated always as (public.ber_ertelmez(bersav) ->> 'deviza') stored,
    add column if not exists ber_egyseg text
        generated always as (public.ber_ertelmez(bersav) ->> 'egyseg') stored,
    add column if not exists ber_min_havi numeric
        generated always as ((public.ber_ertelmez(bersav) ->> 'min_havi')::numeric) stored,
    add column if not exists ber_max_havi numeric
        generated always as ((public.ber_ertelmez(bersav) ->> 'max_havi')::numeric) stored;

create index if not exists hirdetesek_ber_idx
    on public.hirdetesek (szakma_id, ber_deviza, ber_min_havi)
    where ber_min_havi is not null;

-- Az üres string és a NULL keveredése minden számolást elront.
update public.hirdetesek set bersav = null where btrim(bersav) = '';

alter table public.hirdetesek
    drop constraint if exists hirdetesek_bersav_nem_ures;
alter table public.hirdetesek
    add constraint hirdetesek_bersav_nem_ures
        check (bersav is null or length(btrim(bersav)) > 0);
