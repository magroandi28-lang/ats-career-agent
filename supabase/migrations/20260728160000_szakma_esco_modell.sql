-- A szakma-hozzárendelés forrása legyen látható.
--
-- A névegyezés determinisztikus, a modell döntése nem az. Ha a kettő egy
-- oszlopban áll megkülönböztetés nélkül, később nem lehet megmondani,
-- melyik párosítás mennyire megbízható -- és nem lehet célzottan
-- felülvizsgálni sem.
--
-- 'modell': a jelöltlistából választotta ki egy nyelvi modell. A lista
-- kódból készült, és a modell csak sorszámot adhatott vissza, tehát nem
-- találhatott ki nem létező foglalkozást.

alter table public.szakma_esco
    drop constraint if exists szakma_esco_megbizhatosag_check;

alter table public.szakma_esco
    add constraint szakma_esco_megbizhatosag_check check (
        megbizhatosag in ('pontos', 'alternativ', 'kezi', 'modell')
    );
