-- A hirdetésekből kinyert tételek, ahogy a munkáltató leírta őket.
--
-- Ez váltja le a keszsegek/hirdetes_keszseg páros szerepét az illesztésben.
-- A régi lánc öt lépcsőn át gyártott rövid címkéket (kinyerés, kanonizálás,
-- fogalom, szótár, illesztés), és minden lépcső rontott. Itt egyetlen
-- lépcső van: a hirdetés szövegét a saját szerkezete mentén daraboljuk.
--
-- A tábla GENERÁLT: bármikor eldobható és újraszámolható a hirdetésekből.
-- Ezért nincs benne kézzel felvett adat, és ezért törölhető szabadon.

create table if not exists public.hirdetes_tetel (
    id bigint generated always as identity primary key,
    hirdetes_id bigint not null
        references public.hirdetesek(id) on delete cascade,
    -- Denormalizált, hogy a szakmánkénti statisztika egy táblából menjen.
    szakma_id bigint references public.szakmak(id) on delete set null,
    -- Melyik szekcióból származik: ez dönti el, mit kezdünk vele.
    --   feladat  -> ehhez mérjük a CV-t
    --   elvaras  -> ehhez mérjük a CV-t
    --   ajanlat  -> a munkáltató ajánlata; NEM hiányozhat egy CV-ből
    --   egyeb    -> szekciócím előtti rész, jellemzően cégbemutatkozás
    szekcio text not null,
    -- A tétel szó szerint, ahogy a hirdetésben áll. Ezt tudjuk idézni.
    szoveg text not null,
    -- Kisbetűs, ékezet nélküli alak a kereséshez és a csoportosításhoz.
    normalizalt text not null,
    letrehozva timestamptz not null default now(),
    constraint hirdetes_tetel_szekcio_check check (
        szekcio in ('feladat', 'elvaras', 'ajanlat', 'egyeb')
    ),
    constraint hirdetes_tetel_szoveg_nem_ures check (length(szoveg) > 0),
    constraint hirdetes_tetel_normalizalt_nem_ures check (length(normalizalt) > 0)
);

-- Ugyanaz a tétel egy hirdetésen belül egyszer szerepeljen.
create unique index if not exists hirdetes_tetel_egyedi
    on public.hirdetes_tetel(hirdetes_id, szekcio, normalizalt);

-- A szakmánkénti gyakoriság ezen a kettősön fut: „mi jellemző erre a
-- szakmára", illetve „mi az, ami ritka, tehát ennek a hirdetésnek a sajátja".
create index if not exists hirdetes_tetel_szakma_szekcio_idx
    on public.hirdetes_tetel(szakma_id, szekcio);

create index if not exists hirdetes_tetel_normalizalt_idx
    on public.hirdetes_tetel(normalizalt);

alter table public.hirdetes_tetel enable row level security;
alter table public.hirdetes_tetel force row level security;

revoke all on table public.hirdetes_tetel from public, anon, authenticated;
grant all on table public.hirdetes_tetel to service_role;
