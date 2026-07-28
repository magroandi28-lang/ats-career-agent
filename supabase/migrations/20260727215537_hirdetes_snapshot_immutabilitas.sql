-- Utólag mentve az éles migrációs naplóból (20260727215537).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- A már létrehozott V2 snapshot-réteg jogosultság- és immutabilitási
-- szigorítása. Friss telepítésnél az előző migrációval együtt idempotens.

create or replace function private.hirdetes_snapshot_nyers_ved()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
    if (to_jsonb(new) - 'hirdetes_id')
        is distinct from (to_jsonb(old) - 'hirdetes_id') then
        raise exception
            'A hirdetes_snapshot nyers es audit mezoinek modositasa tilos.'
            using errcode = '23514';
    end if;
    return new;
end;
$$;

drop trigger if exists hirdetes_snapshot_nyers_ved
    on public.hirdetes_snapshot;
create trigger hirdetes_snapshot_nyers_ved
before update on public.hirdetes_snapshot
for each row execute function private.hirdetes_snapshot_nyers_ved();

revoke all on function private.hirdetes_snapshot_nyers_ved()
    from public, anon, authenticated, service_role;

revoke all on table public.hirdetes_snapshot from service_role;
revoke all on sequence public.hirdetes_snapshot_id_seq from service_role;
grant select, insert, update on table public.hirdetes_snapshot
    to service_role;
grant usage, select on sequence public.hirdetes_snapshot_id_seq
    to service_role;

