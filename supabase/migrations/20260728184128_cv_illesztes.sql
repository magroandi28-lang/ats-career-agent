-- Utólag mentve az éles migrációs naplóból (20260728184128).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A CV és a szakma ESCO-készséglistájának összevetése.
--
-- NEM PONTOZ. Az ATS nem az ESCO-hoz mér, hanem az adott hirdetéshez; egy
-- valódi állás nem kér 32 készséget, hanem ötöt. Ha a felhasználónak azt
-- írnánk, hogy "32-ből 11 van meg", az egyszerre hamis és elkeserítő.
--
-- Amit ad, három lista:
--   megvan   -- amit a CV-ből felismertünk, ESCO-nyelven megfogalmazva
--              (ez a SZÓKINCS: "raktárban dolgoztam" -> "raktári
--               nyilvántartási rendszereket működtet")
--   kerdes   -- amit érdemes megkérdezni: "ezt is csináltad?"
--              (EMLÉKEZTETŐ, nem számonkérés)
--   forras   -- minden sorhoz az ESCO-URI, hogy visszakereshető legyen
--
-- A szóillesztés ugyanaz az elv, ami a hirdetéscím-besorolónál bevált:
-- a jelentést hordozó szavak előtagja egyezzen, a toldalék leeshet.

create or replace function public.cv_illesztes(
    p_szakma_id bigint,
    p_cv_kifejezesek text[]
)
returns table (
    keszseg_uri text,
    keszseg text,
    kotelezo boolean,
    megvan boolean,
    cv_bizonyitek text
)
language sql
stable
set search_path = public, pg_catalog
as $$
with keszseg as (
    select distinct k.uri, k.nev, fk.kotelezo
    from public.szakma_esco se
    join public.esco_foglalkozas_keszseg fk on fk.foglalkozas_uri = se.foglalkozas_uri
    join public.esco_keszseg k on k.uri = fk.keszseg_uri
    where se.szakma_id = p_szakma_id
),
cv as (
    select kif,
           array(select w from unnest(
                    string_to_array(public.keszseg_normalizal(kif), ' ')) w
                  where length(w) >= 4) as szavak
    from unnest(coalesce(p_cv_kifejezesek, '{}')) kif
),
keszseg_szo as (
    select uri, nev, kotelezo,
           array(select w from unnest(
                    string_to_array(public.keszseg_normalizal(nev), ' ')) w
                  where length(w) >= 4) as szavak
    from keszseg
),
talalat as (
    -- Akkor tekintjük felismertnek, ha a készség MINDEN jelentéses szava
    -- megjelenik a CV-kifejezésben (előtagra illesztve). Ez szigorú, de a
    -- laza illesztés magabiztosan téveszt -- ezt ma megmértük.
    select ks.uri, min(cv.kif) as bizonyitek
    from keszseg_szo ks
    join cv on cardinality(ks.szavak) > 0
           and cardinality(cv.szavak) > 0
           and not exists (
               select 1 from unnest(ks.szavak) kw
                where not exists (
                    select 1 from unnest(cv.szavak) cw
                     where cw like left(kw, greatest(6, length(kw) - 3)) || '%'
                        or kw like left(cw, greatest(6, length(cw) - 3)) || '%')
           )
    group by ks.uri
)
select ks.uri, ks.nev, ks.kotelezo,
       (t.uri is not null) as megvan,
       t.bizonyitek
from keszseg_szo ks
left join talalat t on t.uri = ks.uri
order by ks.kotelezo desc, (t.uri is not null) desc, ks.nev;
$$;

revoke all on function public.cv_illesztes(bigint, text[]) from public, anon, authenticated;
grant execute on function public.cv_illesztes(bigint, text[]) to service_role;
