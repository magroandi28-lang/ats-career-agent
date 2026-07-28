-- Utólag mentve az éles migrációs naplóból (20260728182025).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A tudásbázis témacímkézése, modell nélkül.
--
-- A `tudasanyag` 2 735 szakaszánál az embedding megvan, de a `temak` oszlop
-- ÜRES volt mind a 2 735 sorban. Ezért csak vak vektoros keresés létezett:
-- egy karrierhorgony-kiértékelés is kaphatott kiégésről szóló szakaszt,
-- mert a vektor közel hozta.
--
-- A címkézés kulcsszavakból megy, nem modellel: átlátható, ingyenes, és
-- bármikor újraszámolható. A témakörök a tényleges forrásokból származnak
-- (Hajduska krízislélektan, Selye stressz, Ivey tanácsadás, Gallup,
-- mentálhigiénés kézikönyv, szervezetpszichológia).
create table if not exists public.tema_kulcsszo (
    tema text not null,
    kulcsszo text not null,
    primary key (tema, kulcsszo)
);

alter table public.tema_kulcsszo enable row level security;
alter table public.tema_kulcsszo force row level security;
revoke all on table public.tema_kulcsszo from public, anon, authenticated;
grant all on table public.tema_kulcsszo to service_role;

insert into public.tema_kulcsszo (tema, kulcsszo) values
    ('krizis', 'krízis'), ('krizis', 'krizis'), ('krizis', 'trauma'),
    ('krizis', 'veszteség'), ('krizis', 'gyász'), ('krizis', 'öngyilkos'),
    ('krizis', 'sürgősségi'), ('krizis', 'akut'),

    ('stressz', 'stressz'), ('stressz', 'distressz'), ('stressz', 'kiégés'),
    ('stressz', 'burnout'), ('stressz', 'megküzdés'), ('stressz', 'coping'),
    ('stressz', 'feszültség'), ('stressz', 'kimerül'),

    ('tanacsadas', 'tanácsadás'), ('tanacsadas', 'tanácsadó'),
    ('tanacsadas', 'kliens'), ('tanacsadas', 'interjú'),
    ('tanacsadas', 'empátia'), ('tanacsadas', 'aktív hallgatás'),
    ('tanacsadas', 'kérdezéstechnika'), ('tanacsadas', 'segítő kapcsolat'),

    ('karrier', 'karrier'), ('karrier', 'pályaválasztás'),
    ('karrier', 'pályaorientáció'), ('karrier', 'karrierhorgony'),
    ('karrier', 'életpálya'), ('karrier', 'pályaváltás'),
    ('karrier', 'foglalkozás'), ('karrier', 'hivatás'),

    ('szemelyiseg', 'személyiség'), ('szemelyiseg', 'temperamentum'),
    ('szemelyiseg', 'holland'), ('szemelyiseg', 'típus'),
    ('szemelyiseg', 'vonás'), ('szemelyiseg', 'önismeret'),
    ('szemelyiseg', 'énkép'), ('szemelyiseg', 'identitás'),

    ('motivacio', 'motiváció'), ('motivacio', 'motivál'),
    ('motivacio', 'ösztönz'), ('motivacio', 'szükséglet'),
    ('motivacio', 'elköteleződ'), ('motivacio', 'bevonódás'),

    ('szervezet', 'szervezeti kultúra'), ('szervezet', 'szervezet'),
    ('szervezet', 'vezetés'), ('szervezet', 'vezető'),
    ('szervezet', 'csapat'), ('szervezet', 'munkahelyi'),
    ('szervezet', 'légkör'), ('szervezet', 'konfliktus'),

    ('jollet', 'jóllét'), ('jollet', 'elégedettség'),
    ('jollet', 'mentálhigiéné'), ('jollet', 'egészség'),
    ('jollet', 'életminőség'), ('jollet', 'boldogság'),
    ('jollet', 'work-life'), ('jollet', 'egyensúly'),

    ('erzelem', 'érzelem'), ('erzelem', 'érzelmi'),
    ('erzelem', 'reguláció'), ('erzelem', 'szorongás'),
    ('erzelem', 'düh'), ('erzelem', 'félelem')
on conflict do nothing;

-- A címkézés: minden szakasz megkapja azokat a témákat, amiknek legalább
-- egy kulcsszava szerepel a szövegében. Egy szakasz több témába is
-- tartozhat -- a krízis és az érzelmi reguláció például gyakran együtt jár.
create or replace function public.tudasanyag_cimkezes()
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    darab integer;
begin
    update public.tudasanyag t
       set temak = coalesce(cimke.temak, '{}')
      from (
        select t2.id,
               array_agg(distinct k.tema) filter (where k.tema is not null) as temak
          from public.tudasanyag t2
          left join public.tema_kulcsszo k
                 on lower(t2.szoveg) like '%' || lower(k.kulcsszo) || '%'
         group by t2.id
      ) cimke
     where cimke.id = t.id;
    get diagnostics darab = row_count;
    return darab;
end;
$$;

revoke all on function public.tudasanyag_cimkezes() from public, anon, authenticated;
grant execute on function public.tudasanyag_cimkezes() to service_role;
