-- Utólag mentve az éles migrációs naplóból (20260728183938).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Felhasználói adat: mindenki csak a sajátját.
--
-- Eddig minden táblán be volt kapcsolva az RLS, de EGYETLEN policy sem
-- létezett. Ez ma "működik", mert a backend service_role-lal megy, ami
-- megkerüli az RLS-t -- de ez azt jelenti, hogy a védelem teljes egészében
-- a backend szűrőin múlik. Egy elhibázott lekérdezés keresztbe szivárogtat.
--
-- Ezek a policyk nem törik el a mostani működést (a service_role továbbra is
-- mindent lát), viszont ha a backend user-JWT-vel dolgozik, akkor onnantól
-- az ADATBÁZIS garantálja, hogy senki ne lássa más adatát.
--
-- A public.* táblák (piaci adat) SZÁNDÉKOSAN zárva maradnak: nincs bennük
-- személyes adat, de ez a gyűjtött hirdetésadat a rendszer értéke, nem
-- publikus tartalom.

do $$
declare
    t text;
begin
    foreach t in array array[
        'career_profiles', 'career_profile_snapshots', 'career_workflows',
        'flow_sessions', 'career_gps_events', 'career_gps_snapshots',
        'model_usage', 'active_tasks', 'agent_runs', 'approval_requests',
        'background_jobs', 'audit_events'
    ] loop
        if exists (select 1 from information_schema.columns
                    where table_schema = 'private' and table_name = t
                      and column_name = 'user_id') then
            execute format(
                'drop policy if exists sajat_adat on private.%I', t);
            execute format(
                'create policy sajat_adat on private.%I for all to authenticated '
                'using (user_id = (select auth.uid())) '
                'with check (user_id = (select auth.uid()))', t);
        end if;
    end loop;
end $$;

-- A flow_messages a session-ön keresztül tartozik a felhasználóhoz.
drop policy if exists sajat_uzenet on private.flow_messages;
create policy sajat_uzenet on private.flow_messages for all to authenticated
    using (exists (select 1 from private.flow_sessions s
                    where s.id = flow_messages.session_id
                      and s.user_id = (select auth.uid())))
    with check (exists (select 1 from private.flow_sessions s
                    where s.id = flow_messages.session_id
                      and s.user_id = (select auth.uid())));

-- A Supabase tanácsadója jelezte: a függvénynek nincs rögzítve a
-- search_path-ja. Ez elvben megkerülhetővé teszi egy azonos nevű,
-- másik sémába tett függvénnyel. Egysoros javítás.
alter function public.keszseg_normalizal(text) set search_path = pg_catalog, public;
