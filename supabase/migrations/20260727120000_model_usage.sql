-- Modellhívások költségnaplója.
-- Minden fizetős hívás ide kerül, hogy a keret állása az alkalmazásból
-- látszódjon, ne a szolgáltató fiókjából.
--
-- Szándékosan NEM tárol prompt- vagy válaszszöveget: a naplónak a
-- mennyiséghez és a költséghez van köze, nem a tartalomhoz. Így a
-- költségtörténet személyes adat nélkül megőrizhető.

create table if not exists private.model_usage (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    -- Fióktörléskor a sor megmarad, de gazdátlanná válik: a könyvelésnek
    -- szüksége van rá, a személyhez kötésnek nincs.
    user_id uuid references auth.users(id) on delete set null,
    -- Melyik művelet hívta (pl. flow_valasz, cv_atiras, motivacios_level).
    feladat text not null,
    szolgaltato text not null,
    modell text not null,
    bemeneti_tokenek integer not null default 0,
    kimeneti_tokenek integer not null default 0,
    -- A hívás pillanatában érvényes ártáblázattal számolva. Az ár később
    -- változhat, ezért az akkori költséget rögzítjük, nem számoljuk újra.
    koltseg_usd numeric(12, 6) not null default 0,
    sikeres boolean not null default true,
    -- Rövid hibaok, felhasználói adat nélkül.
    hiba text,
    constraint model_usage_szolgaltato_check check (
        szolgaltato in ('openai', 'gemini')
    ),
    constraint model_usage_bemeneti_tokenek_check check (bemeneti_tokenek >= 0),
    constraint model_usage_kimeneti_tokenek_check check (kimeneti_tokenek >= 0),
    constraint model_usage_koltseg_check check (koltseg_usd >= 0)
);

create index if not exists model_usage_created_idx
    on private.model_usage(created_at desc);

create index if not exists model_usage_user_created_idx
    on private.model_usage(user_id, created_at desc);

-- Napi összesítéshez: ez a lekérdezés fut a költségkijelzőnél.
create index if not exists model_usage_szolgaltato_created_idx
    on private.model_usage(szolgaltato, created_at desc);

alter table private.model_usage enable row level security;
alter table private.model_usage force row level security;

revoke all on table private.model_usage from public, anon, authenticated;
grant all on table private.model_usage to service_role;
