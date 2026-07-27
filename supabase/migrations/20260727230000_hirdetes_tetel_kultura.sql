-- Új szekcióérték: `kultura`.
--
-- A cégjellemző szöveg („nagyszerű vásárlói élményt nyújtani", „Akkor
-- nálunk a helyed!") eddig feladatként vagy egyébként került be. Egyik sem
-- pontos: nem elvégzendő munka, tehát nem hiányozhat egy CV-ből, viszont
-- nem is szemét -- ebből derül ki, milyen munkahelyre készül az ember.
--
-- Mivel minden hirdetéshez tartozik cég, ez cégenként összegyűjthető:
-- mit hangsúlyoz, hogyan szólít meg, mit ígér.

alter table public.hirdetes_tetel
    drop constraint if exists hirdetes_tetel_szekcio_check;

alter table public.hirdetes_tetel
    add constraint hirdetes_tetel_szekcio_check check (
        szekcio in ('feladat', 'elvaras', 'ajanlat', 'kultura', 'egyeb')
    );
