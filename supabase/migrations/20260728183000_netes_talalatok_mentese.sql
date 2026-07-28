-- Utólag mentve az éles migrációs naplóból (20260728183000).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Amit egyszer lekérdezünk a netről, az maradjon meg.
--
-- Ez a "passzív gyűjtés" elve, ami az utils/adatbazis.py fejlécében már ki
-- van mondva: a felhasználói keresések melléktermékeként minden megtalált
-- hirdetést és céget elmentünk. A második felhasználó, aki ugyanarra a cégre
-- kíváncsi, már ingyen kapja.
--
-- Ez azért is fontos, mert az Indeed-kapcsolat a BESZÉLGETÉSEN megy, tehát
-- Andi Claude-keretét fogyasztja. Minden mentett válasz egy meg nem
-- ismételt hívás.
alter table public.hirdetesek
    drop constraint if exists hirdetesek_forras_tipus_check;
alter table public.hirdetesek
    add constraint hirdetesek_forras_tipus_check check (
        forras_tipus in ('portal', 'ceges', 'jooble', 'eures', 'indeed', 'egyeb')
    );

-- Mikor kérdeztük meg utoljára a netet erről a cégről, és honnan.
-- A `ceginfo_frissitve` már létezik; a forrás eddig hiányzott.
alter table public.cegek
    add column if not exists ceginfo_forras text;

comment on column public.cegek.ceginfo_frissitve is
    'Mikor kérdeztük le utoljára külső forrásból. A szabály: előbb az '
    'adatbázis, és csak akkor megyünk a netre, ha nincs adat vagy 30 napnál '
    'régebbi. Minden felesleges lekérdezés pénz vagy keret.';

-- Melyik szakmára nincs egyáltalán hirdetésünk. Ez a "gyorssegély" listája:
-- ha egy átjárhatósági javaslatnál 0 állás jön ki, egy célzott ÉLŐ Jooble-
-- lekérdezés megnézheti, van-e most ilyen -- ingyen, szkriptből.
create or replace view public.v_szakma_hirdetes_nelkul as
select s.id as szakma_id, s.nev as szakma,
       e.foglalkozas_uri, f.nev as esco_nev, f.isco_kod
from public.szakmak s
left join public.szakma_esco e on e.szakma_id = s.id
left join public.esco_foglalkozas f on f.uri = e.foglalkozas_uri
where not exists (
    select 1 from public.hirdetesek h
     where h.szakma_id = s.id and h.allapot = 'aktiv'
);
