-- EURES engedelyezese forras_tipus-kent a hirdetesek tablaban
-- Futtasd le a Supabase SQL Editoraban, egyszer.

alter table hirdetesek drop constraint if exists hirdetesek_forras_tipus_check;
alter table hirdetesek add constraint hirdetesek_forras_tipus_check
    check (forras_tipus in ('portal', 'ceges', 'jooble', 'eures', 'egyeb'));
