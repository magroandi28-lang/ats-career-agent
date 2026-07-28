-- Átjárhatóság: mely szakmákba lehet átlépni a meglévő készségekkel.
--
-- Ez a pályaváltás motorja, és ehhez tényleg kell egy közös, teljes szótár --
-- hirdetésekből nem jön ki, mert két szakma hirdetései sosem ugyanazokkal a
-- szavakkal írják le ugyanazt a készséget. Az ESCO-ban viszont ugyanaz a
-- készség-URI szerepel mindkettőnél, tehát a metszet pontosan számolható.
--
-- Halmazművelet, nulla modellhívás, mindig ugyanaz az eredmény.

-- A túl gyakori készségek kizárása.
--
-- A "vállalati szabályzatokat alkalmaz" 261 foglalkozásban kötelező. Az ilyen
-- készségek nem mondanak semmit az átjárhatóságról: attól, hogy két szakma
-- mindegyike elvárja a szabálykövetést, még nem lehet egyikből a másikba
-- átlépni. A küszöb (50 foglalkozás a 3 039-ből) 220 készséget zár ki a
-- 11 378-ból -- a legáltalánosabb 2%-ot.
create materialized view if not exists public.esco_szomszed as
with hasznos as (
    select fk.foglalkozas_uri, fk.keszseg_uri
    from public.esco_foglalkozas_keszseg fk
    where fk.kotelezo
      and fk.keszseg_uri in (
          select keszseg_uri
          from public.esco_foglalkozas_keszseg
          where kotelezo
          group by keszseg_uri
          having count(*) <= 50
      )
),
darab as (
    select foglalkozas_uri, count(*) n from hasznos group by 1
),
kozos as (
    select a.foglalkozas_uri as innen,
           b.foglalkozas_uri as ide,
           count(*) as kozos_keszseg
    from hasznos a
    join hasznos b
      on b.keszseg_uri = a.keszseg_uri
     and b.foglalkozas_uri <> a.foglalkozas_uri
    group by 1, 2
    -- Három közös készség alatt véletlen egybeesésről van szó.
    having count(*) >= 3
)
select k.innen, k.ide, k.kozos_keszseg,
       di.n as innen_keszseg,
       dk.n as ide_keszseg,
       -- Jaccard: a puszta metszet a sok készséget felsoroló foglalkozásokat
       -- részesítené előnyben. Így az arány számít, nem a méret.
       round(k.kozos_keszseg::numeric
             / nullif(di.n + dk.n - k.kozos_keszseg, 0), 3) as hasonlosag
from kozos k
join darab di on di.foglalkozas_uri = k.innen
join darab dk on dk.foglalkozas_uri = k.ide;

create index if not exists esco_szomszed_innen_idx
    on public.esco_szomszed (innen, hasonlosag desc);
create index if not exists esco_szomszed_ide_idx
    on public.esco_szomszed (ide);
