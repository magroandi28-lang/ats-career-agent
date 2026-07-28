-- Utólag mentve az éles migrációs naplóból (20260728185012).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A KSH hivatalos ISCO-08 <-> FEOR-08 fordítókulcsa.
--
-- Ez oldja meg azt, ami ma reggel elakadt: a FEOR-08 szerkezetileg az
-- ISCO-08-on alapul, de a SZÁMOZÁSA MÁS (ESCO/ISCO 8344 = FEOR 8425;
-- ISCO 5223 = FEOR 5113). Kódon keresztül tippelni nem lehetett, névvel
-- illeszteni pedig veszélyes volt: a szóalapú illesztés a
-- "villamosmérnök"-höz a "Villamosvezető"-t (a járművet) rendelte.
--
-- Forrás: KSH, "A nemzetközi (ISCO-08) és a hazai (FEOR-08) foglalkozási
-- osztályozási rendszerek közötti fordítókulcs"
-- https://www.ksh.hu/docs/osztalyozasok/feor/fordkulcs_isco_feor_hu.pdf
--
-- 534 megfeleltetés, 422 ISCO- és 482 FEOR-kód között. A kapcsolat több a
-- többhöz: egy ISCO-kód több FEOR-ra bomolhat és fordítva.
create table if not exists public.isco_feor (
    isco_kod text not null,
    feor_kod text not null references public.feor_lista(kod),
    isco_nev text,
    feor_nev text,
    primary key (isco_kod, feor_kod)
);

create index if not exists isco_feor_isco_idx on public.isco_feor (isco_kod);
create index if not exists isco_feor_feor_idx on public.isco_feor (feor_kod);

alter table public.isco_feor enable row level security;
alter table public.isco_feor force row level security;
revoke all on table public.isco_feor from public, anon, authenticated;
grant all on table public.isco_feor to service_role;

comment on table public.isco_feor is
    'KSH hivatalos ISCO-08 <-> FEOR-08 fordítókulcs, a fordkulcs_isco_feor_hu.pdf-ből. '
    'Ezen keresztül köthető az ESCO (ISCO-alapú) a KSH béradatához (FEOR-alapú).';
