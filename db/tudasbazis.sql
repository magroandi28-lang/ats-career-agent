-- TUDÁSBÁZIS TÁBLA — futtasd a Supabase SQL Editorban
-- (munka- és szervezetpszichológia szakaszok + keresés jelentés alapján)

-- 1) Vektor-bővítmény bekapcsolása (embedding-kereséshez)
create extension if not exists vector;

-- 2) A tudásbázis tábla
create table if not exists public.tudasanyag (
    id         bigint generated always as identity primary key,
    forras     text not null,            -- pl. 'Corvinus tankönyv (2011)'
    resz       int  not null,            -- hányadik szakasz a forráson belül
    szoveg     text not null,
    temak      text[],                   -- címkék, pl. {karrier, motiváció}
    embedding  vector(768),              -- Gemini text-embedding-004
    letrehozva timestamptz not null default now()
);

alter table public.tudasanyag enable row level security;

-- 3) Kereső index (gyors hasonlóság-keresés)
create index if not exists tudasanyag_embedding_idx
    on public.tudasanyag using hnsw (embedding vector_cosine_ops);

-- 4) Kereső függvény: a kérdéshez legjobban illő szakaszok
create or replace function public.tudas_kereses(
    kerdes_embedding vector(768),
    darab int default 5
)
returns table (id bigint, forras text, szoveg text, hasonlosag float)
language sql stable
as $$
    select t.id, t.forras, t.szoveg,
           1 - (t.embedding <=> kerdes_embedding) as hasonlosag
    from public.tudasanyag t
    where t.embedding is not null
    order by t.embedding <=> kerdes_embedding
    limit darab;
$$;

-- Kész! Ellenőrzés: a Table Editorban megjelenik a 'tudasanyag' tábla.
