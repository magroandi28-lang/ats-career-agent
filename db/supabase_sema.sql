-- ============================================================
-- KARRIER-ÜGYNÖKSÉG — Supabase adatbázis-séma (1. fázis)
--
-- Futtatás: Supabase Dashboard → SQL Editor → új query →
--           illeszd be ezt a fájlt → Run
-- Újrafuttatható: előbb töröl mindent, aztán újraépít.
-- ============================================================

-- ── 0. Takarítás: korábbi kísérleti táblák törlése ──────────
drop table if exists public.job_concept_occurrences cascade;
drop table if exists public.concept_aliases cascade;
drop table if exists public.job_postings cascade;
drop table if exists public.market_concepts cascade;
drop table if exists public.occupations cascade;
drop table if exists public.ingestion_runs cascade;

-- A saját tábláink is (hogy a script bármikor újrafuttatható legyen)
drop view if exists public.v_szakma_keszsegek;
drop view if exists public.v_szakma_attekintes;
drop table if exists public.hirdetes_keszseg cascade;
drop table if exists public.piaci_statisztikak cascade;
drop table if exists public.hirdetesek cascade;
drop table if exists public.keszsegek cascade;
drop table if exists public.cegek cascade;
drop table if exists public.szakmak cascade;

-- ── 1. SZAKMÁK ───────────────────────────────────────────────
-- A szakma_felismeres() eredménye + FEOR-kód a KSH-adatokhoz (4. fázis)
create table public.szakmak (
    id          bigint generated always as identity primary key,
    nev         text not null unique,
    kategoria   text,            -- IT / Egészségügy / Kereskedelem / Ipar / Szolgáltatás / Egyéb
    feor_kod    text,            -- pl. '5113' (bolti eladó) — a KSH-statisztikák kulcsa
    letrehozva  timestamptz not null default now()
);

-- ── 2. CÉGEK (a céginfó-kereső cache-e is!) ──────────────────
create table public.cegek (
    id                bigint generated always as identity primary key,
    nev               text not null unique,
    leiras            text,
    meret             text,
    bersav            text,
    fluktuacio        text,
    velemenyek        text,
    figyelmeztetes    text,
    ceginfo_frissitve timestamptz,   -- mikor kérdeztük le utoljára a SerpAPI-t;
                                     -- ha friss (pl. < 30 nap), nem kérdezzük újra
    letrehozva        timestamptz not null default now()
);

-- ── 3. HIRDETÉSEK ────────────────────────────────────────────
create table public.hirdetesek (
    id           bigint generated always as identity primary key,
    cim          text not null,
    ceg_id       bigint references public.cegek(id)   on delete set null,
    szakma_id    bigint references public.szakmak(id) on delete set null,
    helyszin     text,
    snippet      text,            -- a hirdetés kivonata (feladatok/elvárások nyersen)
    link         text,
    datum_szoveg text,            -- a hirdetésben talált dátum, pl. '2026-05'
    forras_tipus text not null default 'egyeb'
                 check (forras_tipus in ('portal', 'ceges', 'jooble', 'egyeb')),
    bersav       text,            -- ha a hirdetés tartalmaz bérinfót
    letrehozva   timestamptz not null default now()
);

create index idx_hirdetesek_szakma on public.hirdetesek (szakma_id);
create index idx_hirdetesek_ceg    on public.hirdetesek (ceg_id);

-- Duplikátum-védelem: ugyanaz a link csak egyszer kerülhet be
create unique index uq_hirdetes_link
    on public.hirdetesek (link)
    where link is not null and link <> '';

-- ── 4. KÉSZSÉGEK (elvárások, feladatok, eszközök) ────────────
create table public.keszsegek (
    id         bigint generated always as identity primary key,
    nev        text not null unique,   -- MINDIG szakmai néven (pl. 'pénztárgép kezelése')
    tipus      text not null default 'elvaras'
               check (tipus in ('elvaras', 'feladat', 'eszkoz', 'soft')),
    letrehozva timestamptz not null default now()
);

-- ── 5. KAPCSOLÓTÁBLA: melyik hirdetés mit kér ────────────────
create table public.hirdetes_keszseg (
    hirdetes_id bigint not null references public.hirdetesek(id) on delete cascade,
    keszseg_id  bigint not null references public.keszsegek(id)  on delete cascade,
    primary key (hirdetes_id, keszseg_id)
);

-- ── 6. PIACI STATISZTIKÁK (KSH / NFSZ — 4. fázis tölti) ──────
create table public.piaci_statisztikak (
    id         bigint generated always as identity primary key,
    feor_kod   text,
    szakma_id  bigint references public.szakmak(id) on delete set null,
    regio      text,               -- 'Országos', 'Budapest', 'Baranya', ...
    mutato     text not null,      -- pl. 'brutto_atlagkereset', 'allaskeresok_szama'
    ertek      numeric,
    idoszak    text,               -- pl. '2026Q1', '2025'
    forras     text,               -- 'KSH' / 'NFSZ'
    letrehozva timestamptz not null default now(),
    unique (feor_kod, regio, mutato, idoszak, forras)
);

-- ── 7. NÉZETEK az elemzésekhez ───────────────────────────────

-- Szakmánként a leggyakoribb elvárások/feladatok:
-- "a bolti eladó hirdetések 83%-a kéri a HACCP-t"
create or replace view public.v_szakma_keszsegek as
select
    sz.id  as szakma_id,
    sz.nev as szakma,
    k.nev  as keszseg,
    k.tipus,
    count(*) as elofordulas,
    round(
        100.0 * count(*) / nullif(
            (select count(*) from public.hirdetesek h2 where h2.szakma_id = sz.id), 0
        ), 1
    ) as hirdetesek_szazaleka
from public.hirdetesek h
join public.szakmak sz          on sz.id = h.szakma_id
join public.hirdetes_keszseg hk on hk.hirdetes_id = h.id
join public.keszsegek k         on k.id = hk.keszseg_id
group by sz.id, sz.nev, k.nev, k.tipus
order by sz.nev, elofordulas desc;

-- Szakmánkénti áttekintés: hány hirdetés, hány cég, mióta gyűjtünk
create or replace view public.v_szakma_attekintes as
select
    sz.id  as szakma_id,
    sz.nev as szakma,
    sz.kategoria,
    count(h.id)          as hirdetesek_szama,
    count(distinct h.ceg_id) as cegek_szama,
    min(h.letrehozva)    as elso_gyujtes,
    max(h.letrehozva)    as utolso_gyujtes
from public.szakmak sz
left join public.hirdetesek h on h.szakma_id = sz.id
group by sz.id, sz.nev, sz.kategoria
order by hirdetesek_szama desc;

-- ── 8. BIZTONSÁG (RLS) ───────────────────────────────────────
-- Minden táblán bekapcsoljuk a Row Level Security-t.
-- A Python backend a SERVICE_ROLE kulccsal ír/olvas, ami megkerüli
-- az RLS-t — így külön policy nélkül is működik, kívülről viszont
-- senki nem fér az adatokhoz. (Auth majd később, ha lesz fiók.)
alter table public.szakmak            enable row level security;
alter table public.cegek              enable row level security;
alter table public.hirdetesek         enable row level security;
alter table public.keszsegek          enable row level security;
alter table public.hirdetes_keszseg   enable row level security;
alter table public.piaci_statisztikak enable row level security;

-- Kész! Ellenőrzés: Table Editor-ban 6 táblát kell látnod.
