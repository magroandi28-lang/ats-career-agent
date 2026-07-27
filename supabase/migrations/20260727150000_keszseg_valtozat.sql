-- CV-oldali készség-szinonimaszótár.
--
-- A hirdetésekben mért készségeknek megvan a kanonikus nevük és a
-- gyűjtőfogalmuk. Ami hiányzott: ahogy a felhasználó a CV-jében ÍRJA
-- ugyanazt („kasszáztam" = „pénztárkezelés").
--
-- Ez váltja ki a modellhívást az ATS-felismerésből: ugyanarra a CV-re
-- mindig ugyanaz az eredmény, nulla költséggel, és ami hiányzik belőle,
-- az látható és javítható.

-- A normalizálás egyetlen helyen van definiálva, hogy a feltöltés és a
-- keresés biztosan ugyanúgy számoljon. Kisbetű, ékezet nélkül, csak betű,
-- szám, szóköz és kötőjel marad, a szóközök egybevonva.
create or replace function public.keszseg_normalizal(szoveg text)
returns text
language sql
immutable
as $$
    select trim(regexp_replace(
        regexp_replace(
            translate(lower(coalesce(szoveg, '')),
                      'áéíóöőúüű', 'aeiooouuu'),
            '[^a-z0-9 -]', ' ', 'g'),
        '\s+', ' ', 'g'))
$$;

create table if not exists public.keszseg_valtozat (
    id bigint generated always as identity primary key,
    keszseg_id bigint not null
        references public.keszsegek(id) on delete cascade,
    -- Ahogy a szöveg ténylegesen szerepelhet egy CV-ben.
    valtozat text not null,
    -- A keresés ezen fut; a fenti függvény állítja elő.
    normalizalt text not null,
    -- 'mag': a meglévő készségnevekből generált
    -- 'kezi': ember vette fel
    -- 'tanult': fel nem ismert CV-kifejezésből, jóváhagyás után
    forras text not null default 'kezi',
    created_at timestamptz not null default now(),
    constraint keszseg_valtozat_forras_check
        check (forras in ('mag', 'kezi', 'tanult')),
    constraint keszseg_valtozat_normalizalt_nem_ures
        check (length(normalizalt) > 0)
);

-- Egy kifejezés egy készséget jelentsen: a többértelműség a felismerésnél
-- eldönthetetlen lenne.
create unique index if not exists keszseg_valtozat_normalizalt_egyedi
    on public.keszseg_valtozat(normalizalt);

create index if not exists keszseg_valtozat_keszseg_idx
    on public.keszseg_valtozat(keszseg_id);

-- Magfeltöltés a már meglévő adatból: minden készség saját neve és
-- kanonikus alakja egyben változat is.
--
-- A `fogalom` szándékosan kimarad: egy gyűjtőfogalom (pl. „áru- és
-- készletkezelés") több tucat készséghez tartozik, így nem lehetne
-- eldönteni, melyikre illessze a találatot.
insert into public.keszseg_valtozat (keszseg_id, valtozat, normalizalt, forras)
select k.id, v.szoveg, public.keszseg_normalizal(v.szoveg), 'mag'
from public.keszsegek k
cross join lateral (values (k.nev), (k.kanonikus)) as v(szoveg)
where v.szoveg is not null
  and public.keszseg_normalizal(v.szoveg) <> ''
on conflict (normalizalt) do nothing;
