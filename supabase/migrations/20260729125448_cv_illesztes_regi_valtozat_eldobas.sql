-- A `p_szo_kuszob` parameter hozzaadasa uj tulterhelest hozott letre a regi
-- harom parameteres valtozat mellett. Ket azonos nevu fuggveny kozul a
-- Postgres nem tud valasztani ("function is not unique"), es a hivo hibat
-- kap. A regi valtozat mar nem kell -- azt a `keszseg_db` mereshez kotott
-- szoszures valtotta le.
drop function if exists public.cv_illesztes(bigint, text[], numeric);