-- FEOR referencia-tábla + a szakmak tábla összekötése vele
-- Futtasd le a Supabase SQL Editorában, egyszer.

create table if not exists feor_lista (
    kod text primary key,
    nev text not null
);

alter table szakmak add column if not exists feor_kod text references feor_lista(kod);
