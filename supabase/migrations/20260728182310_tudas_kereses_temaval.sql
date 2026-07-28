-- Utólag mentve az éles migrációs naplóból (20260728182310).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Témára szűrt tudáskeresés.
--
-- A `tudas_kereses` vakon keres az egész anyagban: egy karrierhorgony-
-- kiértékelés is kaphat kiégésről szóló szakaszt, mert a vektor közel hozza.
-- Most, hogy a `temak` fel van töltve, a keresés célozható.
--
-- A régi függvény VÁLTOZATLAN marad, hogy a meglévő hívások ne törjenek el.
--
-- A `temak` üres tömbje azt jelenti: ne szűrj. A visszaadott `temak` mező
-- azért kell, hogy látszódjon, MIÉRT jött vissza egy szakasz -- a válasz így
-- megindokolható, nem fekete doboz.
create or replace function public.tudas_kereses_temaval(
    kerdes_embedding vector,
    temak_szuro text[] default '{}',
    darab integer default 5
)
returns table (id bigint, forras text, szoveg text, temak text[], hasonlosag double precision)
language sql
stable
set search_path = pg_catalog, public, extensions
as $$
    select t.id, t.forras, t.szoveg, t.temak,
           1 - (t.embedding <=> kerdes_embedding) as hasonlosag
    from public.tudasanyag t
    where t.embedding is not null
      and (cardinality(temak_szuro) = 0 or t.temak && temak_szuro)
    order by t.embedding <=> kerdes_embedding
    limit darab;
$$;

create index if not exists tudasanyag_temak_idx on public.tudasanyag using gin (temak);

revoke all on function public.tudas_kereses_temaval(vector, text[], integer)
    from public, anon, authenticated;
grant execute on function public.tudas_kereses_temaval(vector, text[], integer)
    to service_role;
