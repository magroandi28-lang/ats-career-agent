-- Utólag mentve az éles migrációs naplóból (20260727220004).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A karantén és a listázási kapu ne kerülhessen ellentmondó állapotba.

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.hirdetes_snapshot'::regclass
          and conname = 'hirdetes_snapshot_listazas_check'
    ) then
        alter table public.hirdetes_snapshot
            add constraint hirdetes_snapshot_listazas_check check (
                listazasra_alkalmas
                = (validacios_allapot = 'elfogadott')
            );
    end if;
end;
$$;

