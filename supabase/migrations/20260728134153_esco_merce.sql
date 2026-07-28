-- ESCO: a mérce.
--
-- Miért kell: a hirdetésekből nem lehet teljes elvárás-listát kinyerni --
-- a szövegük 258 karakteres kivonat, és a forrás nem ad többet (mérve:
-- Jooble 403, EURES üres HTML, a Jooble API-nak nincs teljes leírás mezője).
-- Az ESCO viszont foglalkozásonként adja a feladatokat és készségeket,
-- hivatalosan, magyarul, 3 043 foglalkozásra.
--
-- A két réteg NEM olvad össze. Megmérve: az ESCO készségnevei
-- sztringilleszkedéssel nem találhatók meg a hirdetésekben (32-ből 9, és
-- az is zaj), mert a magyar ESCO-készségeknek nincs alternatív nevük --
-- csak a hivatalos megfogalmazás. A két réteg a SZAKMA szintjén kapcsolódik,
-- ott van közös kulcs.
--
--   ESCO      -> mi tartozik a szakmához (a mérce)
--   hirdetés  -> mit kér ebből a magyar piac most (a valóság)
--   különbség -> ez maga a tanács és a fejlődési irány
--
-- Nulla modellhívás: a betöltés CSV-ből megy, a szakma-hozzárendelés
-- normalizált névegyezéssel.

-- ── Foglalkozások ────────────────────────────────────────────
create table if not exists public.esco_foglalkozas (
    uri text primary key,
    -- Az ISCO-08 kód. A FEOR-08 ennek a magyar adaptációja, tehát ezen
    -- keresztül köthető a `feor_lista` és a KSH-béradat.
    isco_kod text,
    isco_csoport text,
    nev text not null,
    -- Ahogy a foglalkozást még hívják ("szcenikus", "filmtechnikus").
    -- A foglalkozásoknál VAN alternatív név -- a készségeknél nincs.
    alt_nevek text[] not null default '{}',
    leiras text,
    normalizalt text not null
        generated always as (public.keszseg_normalizal(nev)) stored
);

create index if not exists esco_foglalkozas_isco_idx
    on public.esco_foglalkozas (isco_kod);
create index if not exists esco_foglalkozas_norm_idx
    on public.esco_foglalkozas (normalizalt);

-- ── Készségek ────────────────────────────────────────────────
create table if not exists public.esco_keszseg (
    uri text primary key,
    nev text not null,
    -- 'skill/competence' vagy 'knowledge': a tudás és a tevékenység
    -- külön kezelendő, mert a CV-ben is máshogy jelenik meg.
    tipus text,
    ujrahasznosithatosag text,
    leiras text,
    normalizalt text not null
        generated always as (public.keszseg_normalizal(nev)) stored
);

create index if not exists esco_keszseg_norm_idx
    on public.esco_keszseg (normalizalt);

-- ── Melyik foglalkozáshoz mi tartozik ────────────────────────
create table if not exists public.esco_foglalkozas_keszseg (
    foglalkozas_uri text not null
        references public.esco_foglalkozas(uri) on delete cascade,
    keszseg_uri text not null
        references public.esco_keszseg(uri) on delete cascade,
    -- true: 'essential' (kötelező), false: 'optional' (opcionális).
    -- A kettő különbsége a tanácsadásban számít: a kötelező a belépő,
    -- az opcionális a fejlődési irány.
    kotelezo boolean not null,
    primary key (foglalkozas_uri, keszseg_uri)
);

create index if not exists esco_fk_keszseg_idx
    on public.esco_foglalkozas_keszseg (keszseg_uri);

-- ── A saját szakmáink hozzárendelése ─────────────────────────
-- Több a többhöz: a "bolti eladó" 30 ESCO-foglalkozásra illik
-- (élelmiszer, ruházat, vasáru…), a "targoncavezető" egyre.
create table if not exists public.szakma_esco (
    szakma_id bigint not null
        references public.szakmak(id) on delete cascade,
    foglalkozas_uri text not null
        references public.esco_foglalkozas(uri) on delete cascade,
    -- 'pontos'     : a szakma neve = az ESCO preferált neve
    -- 'alternativ' : a szakma neve az ESCO alternatív nevei között van
    -- 'kezi'       : ember rendelte hozzá
    megbizhatosag text not null
        check (megbizhatosag in ('pontos', 'alternativ', 'kezi')),
    letrehozva timestamptz not null default now(),
    primary key (szakma_id, foglalkozas_uri)
);

create index if not exists szakma_esco_foglalkozas_idx
    on public.szakma_esco (foglalkozas_uri);

-- ── Biztonság ────────────────────────────────────────────────
-- Ugyanaz a minta, mint a `hirdetes_tetel`-nél: a backend service_role-lal
-- ír és olvas, kívülről semmi nem érhető el.
alter table public.esco_foglalkozas          enable row level security;
alter table public.esco_keszseg              enable row level security;
alter table public.esco_foglalkozas_keszseg  enable row level security;
alter table public.szakma_esco               enable row level security;

alter table public.esco_foglalkozas          force row level security;
alter table public.esco_keszseg              force row level security;
alter table public.esco_foglalkozas_keszseg  force row level security;
alter table public.szakma_esco               force row level security;

revoke all on table public.esco_foglalkozas          from public, anon, authenticated;
revoke all on table public.esco_keszseg              from public, anon, authenticated;
revoke all on table public.esco_foglalkozas_keszseg  from public, anon, authenticated;
revoke all on table public.szakma_esco               from public, anon, authenticated;

grant all on table public.esco_foglalkozas          to service_role;
grant all on table public.esco_keszseg              to service_role;
grant all on table public.esco_foglalkozas_keszseg  to service_role;
grant all on table public.szakma_esco               to service_role;
