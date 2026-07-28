-- Utólag mentve az éles migrációs naplóból (20260728182846).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A csoportszintű mérce küszöbe: mérve, nem tippelve.
--
-- 50%-os küszöbbel a 81-es ISCO-csoport (gépkezelők) ÜRES eredményt adott:
-- a ~100 gépkezelő szakma túl különböző, nincs olyan készség, ami a felében
-- megvolna. 15%-kal viszont értelmes mag jön elő: minőségi szabványok (27%),
-- hibaelhárítás (26%), a gép táplálása (23%), a vezérlőegység beállítása
-- (20%), védőfelszerelés (19%).
--
-- EZÉRT AZ `arany` MEZŐT MINDIG KI KELL ÍRNI. Ezek nem "kötelező"
-- készségek -- ilyen a csoportban nincs --, hanem a csoportban
-- LEGGYAKORIBBAK. Aki 27%-ot 100%-ként mutat, az hazudik.
create or replace function public.isco_csoport_keszsegei(
    elotag text, min_arany numeric default 0.15
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

comment on table public.hirdetes_snapshot is
    'ÜRES ÉS EGYELŐRE NEM HASZNÁLT (2026-07-28). A teljes szövegű hirdetések '
    'hiteles tárolására készült, de mérve kiderült, hogy nincs ingyenes '
    'teljes szövegű magyar forrás (Jooble 403, EURES JS-oldal, a Jooble '
    'API-nak nincs teljes leírás mezője). A tábla megmarad: ha egyszer lesz '
    'ilyen forrás, ez a helye. Addig ne épüljön rá funkció.';
