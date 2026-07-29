-- Napi idősor-pillanatkép: az alap, amire később idősorelemzés épülhet.
--
-- MIÉRT MOST, HA MÉG NEM HASZNÁLJUK: fluktuációt ma nem lehet mérni.
-- 2026-07-29-én 16 nap adat van (07-14 óta), STL-dekompozícióhoz legalább két
-- teljes szezonális periódus kell -- heti mintázathoz 4-6 hét, fluktuációról
-- bármit állítani hónapok. Az idősor viszont csak akkor lesz meg három hónap
-- múlva, ha MA elkezdjük gyűjteni. Ez ma egy sor szakmánként, akkor kilencven.
--
-- MIÉRT ÁLLAPOT ÉS NEM KÜLÖNBSÉG: napi állapotot tárolunk (hány aktív, hány
-- új), nem előre kiszámolt változást. A különbség az állapotból bármikor
-- visszaszámolható, fordítva nem -- és egy kimaradt nap így nem rontja el az
-- egész sorozatot, csak lyukat üt bele.
--
-- A `visszamenoleg` oszlop azt jelöli, hogy a sor NEM mérés, hanem utólagos
-- rekonstrukció. A múltról csak az `uj_hirdetes` ismerhető pontosan (az
-- `eloszor_latva`-ból); hogy egy adott napon mennyi volt AKTÍV, azt
-- visszamenőleg nem tudjuk -- ezért nem is találjuk ki, NULL marad.
-- Rekonstruált és mért adatot egy oszlopban keverni az a fajta csendes
-- hazugság, amit később senki nem vesz észre.

create table if not exists public.napi_szakma_pillanatkep (
    nap date not null,
    szakma_id bigint not null references public.szakmak(id) on delete cascade,
    aktiv_hirdetes integer,
    uj_hirdetes integer not null default 0,
    ceg_db integer,
    ber_median numeric,
    ber_mintaszam integer,
    visszamenoleg boolean not null default false,
    primary key (nap, szakma_id)
);

create table if not exists public.napi_ceg_pillanatkep (
    nap date not null,
    ceg_id bigint not null references public.cegek(id) on delete cascade,
    aktiv_hirdetes integer,
    uj_hirdetes integer not null default 0,
    szakma_db integer,
    ber_median numeric,
    visszamenoleg boolean not null default false,
    primary key (nap, ceg_id)
);

alter table public.napi_szakma_pillanatkep enable row level security;
alter table public.napi_szakma_pillanatkep force row level security;
revoke all on table public.napi_szakma_pillanatkep from public, anon, authenticated;
grant all on table public.napi_szakma_pillanatkep to service_role;

alter table public.napi_ceg_pillanatkep enable row level security;
alter table public.napi_ceg_pillanatkep force row level security;
revoke all on table public.napi_ceg_pillanatkep from public, anon, authenticated;
grant all on table public.napi_ceg_pillanatkep to service_role;

create index if not exists napi_szakma_pillanatkep_szakma_idx
    on public.napi_szakma_pillanatkep (szakma_id, nap);
create index if not exists napi_ceg_pillanatkep_ceg_idx
    on public.napi_ceg_pillanatkep (ceg_id, nap);


-- A mai állapot rögzítése. Idempotens: ugyanarra a napra újrafuttatva
-- felülír, nem duplikál -- így egy megismételt karbantartás nem torzít.
--
-- A bér-medián ugyanazzal a szabállyal számol, mint a `v_szakma_kereset`
-- (`ber_min_havi`, csak HUF). Ha itt máshogy számolnánk, az idősor nem lenne
-- összevethető azzal, amit a felhasználó a piaci körképben lát.
create or replace function public.napi_pillanatkep(p_nap date default current_date)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    szakma_sor integer;
    ceg_sor integer;
begin
    insert into public.napi_szakma_pillanatkep as t
        (nap, szakma_id, aktiv_hirdetes, uj_hirdetes, ceg_db,
         ber_median, ber_mintaszam, visszamenoleg)
    select p_nap,
           h.szakma_id,
           count(*) filter (where h.allapot = 'aktiv'),
           count(*) filter (where h.eloszor_latva::date = p_nap),
           count(distinct h.ceg_id) filter (where h.allapot = 'aktiv'),
           round(percentile_cont(0.5) within group (
               order by h.ber_min_havi)
               filter (where h.ber_deviza = 'HUF' and h.ber_min_havi is not null)),
           count(*) filter (where h.ber_min_havi is not null),
           false
      from public.hirdetesek h
     where h.szakma_id is not null
     group by h.szakma_id
    on conflict (nap, szakma_id) do update
       set aktiv_hirdetes = excluded.aktiv_hirdetes,
           uj_hirdetes    = excluded.uj_hirdetes,
           ceg_db         = excluded.ceg_db,
           ber_median     = excluded.ber_median,
           ber_mintaszam  = excluded.ber_mintaszam,
           visszamenoleg  = false;
    get diagnostics szakma_sor = row_count;

    insert into public.napi_ceg_pillanatkep as t
        (nap, ceg_id, aktiv_hirdetes, uj_hirdetes, szakma_db,
         ber_median, visszamenoleg)
    select p_nap,
           h.ceg_id,
           count(*) filter (where h.allapot = 'aktiv'),
           count(*) filter (where h.eloszor_latva::date = p_nap),
           count(distinct h.szakma_id) filter (where h.allapot = 'aktiv'),
           round(percentile_cont(0.5) within group (
               order by h.ber_min_havi)
               filter (where h.ber_deviza = 'HUF' and h.ber_min_havi is not null)),
           false
      from public.hirdetesek h
     where h.ceg_id is not null
     group by h.ceg_id
    on conflict (nap, ceg_id) do update
       set aktiv_hirdetes = excluded.aktiv_hirdetes,
           uj_hirdetes    = excluded.uj_hirdetes,
           szakma_db      = excluded.szakma_db,
           ber_median     = excluded.ber_median,
           visszamenoleg  = false;
    get diagnostics ceg_sor = row_count;

    return jsonb_build_object('nap', p_nap,
                              'szakma_sor', szakma_sor,
                              'ceg_sor', ceg_sor);
end;
$$;

revoke all on function public.napi_pillanatkep(date) from public, anon, authenticated;
grant execute on function public.napi_pillanatkep(date) to service_role;

comment on function public.napi_pillanatkep(date) is
    'Napi allapot-pillanatkep szakmankent es cegenkent, idosorelemzeshez. '
    'Idempotens. A napi_karbantartas() hivja 08:00 UTC-kor, a gyujtes utan.';


-- VISSZAMENŐLEGES REKONSTRUKCIÓ, egyszeri.
--
-- Csak az `uj_hirdetes` kerül bele, mert az `eloszor_latva`-ból pontosan
-- ismert. Az aznapi aktív állomány NEM ismerhető visszamenőleg, ezért NULL
-- marad, és a sor `visszamenoleg = true` jelölést kap. Így az elemzés tudni
-- fogja, hogy 2026-07-29 előtt csak a beáramlás mérhető, az állomány nem.
insert into public.napi_szakma_pillanatkep
    (nap, szakma_id, uj_hirdetes, visszamenoleg)
select h.eloszor_latva::date, h.szakma_id, count(*), true
  from public.hirdetesek h
 where h.szakma_id is not null
   and h.eloszor_latva::date < current_date
 group by 1, 2
on conflict (nap, szakma_id) do nothing;

insert into public.napi_ceg_pillanatkep
    (nap, ceg_id, uj_hirdetes, visszamenoleg)
select h.eloszor_latva::date, h.ceg_id, count(*), true
  from public.hirdetesek h
 where h.ceg_id is not null
   and h.eloszor_latva::date < current_date
 group by 1, 2
on conflict (nap, ceg_id) do nothing;


-- Bekötés a napi karbantartásba. A pillanatkép a lejáratozás UTÁN kell, hogy
-- készüljön -- az `allapot` oszlopból olvas, tehát ha előbb futna, a tegnapi
-- állapotot rögzítené. A lejáratozás a söprés végén megy (04:00 körül), a
-- karbantartás 08:00-kor: a sorrend eleve helyes.
create or replace function public.napi_karbantartas()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
    cimkezett integer;
    pillanatkep jsonb;
begin
    cimkezett := public.tudasanyag_cimkezes();
    perform public.nezetek_frissitese();
    pillanatkep := public.napi_pillanatkep();
    return jsonb_build_object('ujracimkezett_szakasz', cimkezett,
                              'pillanatkep', pillanatkep);
end;
$$;

comment on function public.napi_karbantartas() is
    'Tudasanyag-cimkezes + nezetfrissites + napi idosor-pillanatkep. '
    'A LEJARATOZAS NEM ITT VAN: az a sopres vegen fut, kozvetlenul a '
    'lattamozas utan, kulonben rossz sorrendben jelolne eltuntnek elo '
    'hirdeteseket. pg_cron 08:00 UTC.';
