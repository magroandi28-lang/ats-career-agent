-- Ugyanaz az állás, több linken.
--
-- A `uq_hirdetes_link` csak azt akadályozza meg, hogy ugyanaz a LINK
-- kétszer bekerüljön. De ugyanazt az állást a portálok több linken is
-- kiadják, és a söprés (megyénként, átfedő városokkal) ezt fel is hozza.
-- Mérve: 1 017 olyan (cím, cég, helyszín) hármas volt, ami többször
-- szerepelt.
--
-- Miért baj: az elvárás-statisztika azon alapul, hány HIRDETÉSBEN szerepel
-- egy kifejezés. Egy ötször felrakott állás ötszörös súlyt kap, és úgy tűnik,
-- mintha a piac ötször kérné ugyanazt.
--
-- A duplikátumot NEM töröljük -- az is információ, hogy egy cég sokszor
-- hirdeti ugyanazt (ez a fluktuáció jelzése, lásd a cégprofilt). Csak nem
-- számoljuk többször.

-- md5 és nem sha256: a sha256 bytea-t vár, a `convert_to` átalakítás pedig
-- csak STABLE (a szerver kódolásától függ), ezért generált oszlopba nem
-- tehető. Ujjlenyomatnak ez bőven elég -- nem titkosítunk, csak azonosat
-- keresünk azonossal.
alter table public.hirdetesek
    add column if not exists tartalom_kulcs text
    generated always as (
        md5(
            regexp_replace(lower(btrim(cim)), '\s+', ' ', 'g')
            || '|' || coalesce(ceg_id::text, '?')
            || '|' || regexp_replace(lower(btrim(coalesce(helyszin, ''))), '\s+', ' ', 'g')
        )
    ) stored;

create index if not exists hirdetesek_tartalom_kulcs_idx
    on public.hirdetesek (tartalom_kulcs);

comment on column public.hirdetesek.tartalom_kulcs is
    'Tartalmi ujjlenyomat: cím + cég + helyszín. Minden gyakorisági '
    'statisztika count(distinct tartalom_kulcs)-ot számoljon, ne count(*)-ot.';
