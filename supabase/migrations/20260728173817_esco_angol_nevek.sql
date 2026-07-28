-- Angol foglalkozásnevek: sok multi angolul hirdet.
--
-- A Zala-próbán a be nem sorolt hirdetések nagy része angol című volt
-- ("B2B Sales Specialist", "Head of Maintenance", "Simulation Engineer").
-- A besoroló szótára csak magyar volt, ezért ezek kimaradtak.
--
-- Az ESCO angol csomagja UGYANAZOKAT az URI-kat használja, és a
-- foglalkozás-készség kapcsolatok nyelvfüggetlenek -- tehát csak a neveket
-- kell hozzátenni, semmit nem kell újratölteni. Betöltés:
--     python scripts/esco_betolto.py --angol "…en - csv.zip"
-- (vagy `--angol-api`, ha a ZIP nincs kéznél)
alter table public.esco_foglalkozas
    add column if not exists nev_en text,
    add column if not exists alt_nevek_en text[] not null default '{}';

-- A névlista mostantól kétnyelvű. A `nyelv` oszlop azért kell, hogy meg
-- lehessen mondani, melyik névből lett a találat -- a besorolás így
-- megmagyarázható marad, nem fekete doboz.
drop materialized view if exists public.esco_nev;

create materialized view public.esco_nev as
select f.uri,
       n.nev,
       public.keszseg_normalizal(n.nev) as normalizalt,
       n.preferalt,
       n.nyelv
from public.esco_foglalkozas f,
     lateral (
         select nev, true as preferalt, 'hu' as nyelv from unnest(array[f.nev]) as t(nev)
         union all
         select nev, false, 'hu' from unnest(f.alt_nevek) as t(nev)
         union all
         select nev, true, 'en' from unnest(array[f.nev_en]) as t(nev) where f.nev_en is not null
         union all
         select nev, false, 'en' from unnest(f.alt_nevek_en) as t(nev)
     ) n
where public.keszseg_normalizal(n.nev) <> '';

create index esco_nev_normalizalt_idx on public.esco_nev (normalizalt);
create index esco_nev_uri_idx on public.esco_nev (uri);
