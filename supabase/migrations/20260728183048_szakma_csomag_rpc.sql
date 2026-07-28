-- Utólag mentve az éles migrációs naplóból (20260728183048).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Amit a nyelvi modell lát: EGY csomag, forrásmegjelöléssel.
--
-- Az elv: a modell soha ne kapjon nyers táblát, csak kész, idézhető adatot,
-- amihez oda van írva, mennyire megbízható. Így nem tud kitalálni -- ami
-- nincs a csomagban, arról nincs mit mondania.
--
-- A bizalmi szintek KÉRDÉSENKÉNT szólnak: egy szakmáról lehet tudni, hogy
-- van rá kereslet, miközben a béréről nincs elég adat. Ezt ki kell mondani,
-- nem elhallgatni.
create or replace function public.szakma_csomag(p_szakma_id bigint)
returns jsonb
language sql
stable
set search_path = public, pg_catalog
as $$
select jsonb_build_object(
  'szakma',    (select nev from public.szakmak where id = p_szakma_id),
  'lefedettseg', (
      select to_jsonb(l) - 'szakma_id'
      from public.mv_szakma_lefedettseg l where l.szakma_id = p_szakma_id),
  'esco', (
      select jsonb_agg(jsonb_build_object(
                 'nev', f.nev, 'isco', f.isco_kod, 'leiras', f.leiras,
                 'kotelezo_keszseg', (
                     select count(*) from public.esco_foglalkozas_keszseg fk
                      where fk.foglalkozas_uri = f.uri and fk.kotelezo)))
      from public.szakma_esco se
      join public.esco_foglalkozas f on f.uri = se.foglalkozas_uri
      where se.szakma_id = p_szakma_id),
  'ber', (
      select jsonb_build_object(
          'hirdetett_median', k.hirdetett_median,
          'hirdetett_mintaszam', k.hirdetett_mintaszam,
          'ksh_atlagkereset', k.ksh_atlagkereset,
          'ksh_idoszak', k.ksh_idoszak,
          -- A KSH-adat 2024-es, a hirdetések 2026-osak. Ezt ki KELL írni,
          -- különben két év inflációt hallgatunk el.
          'figyelmeztetes', 'A KSH-adat és a hirdetések eltérő időszakból valók.')
      from public.v_szakma_kereset k where k.szakma_id = p_szakma_id limit 1),
  'szomszedok', (
      select jsonb_agg(x) from (
          select f2.nev as szakma, sz.kozos_keszseg, sz.hasonlosag,
                 (select count(distinct h.tartalom_kulcs)
                    from public.hirdetesek h
                    join public.szakma_esco se2 on se2.szakma_id = h.szakma_id
                   where se2.foglalkozas_uri = sz.ide and h.allapot = 'aktiv') as allas
          from public.szakma_esco se
          join public.esco_szomszed sz on sz.innen = se.foglalkozas_uri
          join public.esco_foglalkozas f2 on f2.uri = sz.ide
          where se.szakma_id = p_szakma_id
          order by sz.hasonlosag desc limit 5) x),
  'frissesseg', (
      select max(utoljara_latva) from public.hirdetesek
       where szakma_id = p_szakma_id)
) $$;

revoke all on function public.szakma_csomag(bigint) from public, anon, authenticated;
grant execute on function public.szakma_csomag(bigint) to service_role;
