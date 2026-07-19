-- KÉPZÉSEK TÁBLA — futtasd a Supabase SQL Editorban
create table if not exists public.kepzesek (
    id          bigint generated always as identity primary key,
    terulet     text not null,      -- it / data / kereskedelem / nyelvi / altalanos
    nev         text not null unique,
    szolgaltato text,
    link        text,
    idotartam   text,
    ar          text,
    miert_jo    text,
    aktiv       boolean not null default true,
    letrehozva  timestamptz not null default now()
);

alter table public.kepzesek enable row level security;
