-- Utólag mentve az éles migrációs naplóból (20260724162459).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Verziózott karrierprofil-alap. Közvetlen böngészős hozzáférés nincs.

create table if not exists private.career_profiles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references auth.users(id) on delete cascade,
    draft_data jsonb not null default '{}'::jsonb,
    draft_version integer not null default 0 check (draft_version >= 0),
    confirmed_data jsonb not null default '{}'::jsonb,
    active_snapshot_id uuid,
    rule_version text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint career_profiles_draft_object check (
        jsonb_typeof(draft_data) = 'object'
    ),
    constraint career_profiles_confirmed_object check (
        jsonb_typeof(confirmed_data) = 'object'
    )
);

create table if not exists private.career_profile_snapshots (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references private.career_profiles(id)
        on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    version integer not null check (version > 0),
    data jsonb not null,
    reason text not null check (char_length(reason) between 1 and 100),
    source_draft_version integer not null check (source_draft_version >= 0),
    rule_version text not null,
    created_at timestamptz not null default now(),
    unique (profile_id, version),
    constraint career_profile_snapshots_data_object check (
        jsonb_typeof(data) = 'object'
    )
);

alter table private.career_profiles
    add constraint career_profiles_active_snapshot_fk
    foreign key (active_snapshot_id)
    references private.career_profile_snapshots(id)
    on delete set null;

create index if not exists career_profile_snapshots_user_version_idx
    on private.career_profile_snapshots(user_id, version desc);

alter table private.career_profiles enable row level security;
alter table private.career_profiles force row level security;
alter table private.career_profile_snapshots enable row level security;
alter table private.career_profile_snapshots force row level security;

revoke all on table private.career_profiles from public, anon, authenticated;
revoke all on table private.career_profile_snapshots
    from public, anon, authenticated;
grant all on table private.career_profiles to service_role;
grant all on table private.career_profile_snapshots to service_role;

create or replace function private.confirm_career_profile(
    p_user_id uuid,
    p_expected_draft_version integer,
    p_confirmed_data jsonb,
    p_reason text,
    p_rule_version text
)
returns setof private.career_profile_snapshots
language plpgsql
security definer
set search_path = ''
as $$
declare
    locked_profile private.career_profiles;
    next_version integer;
    created_snapshot private.career_profile_snapshots;
begin
    if jsonb_typeof(p_confirmed_data) <> 'object' then
        raise exception 'confirmed_data must be an object';
    end if;

    select *
      into locked_profile
      from private.career_profiles
     where user_id = p_user_id
     for update;

    if not found then
        raise exception 'career profile not found';
    end if;
    if locked_profile.draft_version <> p_expected_draft_version then
        raise exception 'career profile draft changed';
    end if;

    select coalesce(max(version), 0) + 1
      into next_version
      from private.career_profile_snapshots
     where profile_id = locked_profile.id;

    insert into private.career_profile_snapshots (
        profile_id, user_id, version, data, reason,
        source_draft_version, rule_version
    ) values (
        locked_profile.id, p_user_id, next_version, p_confirmed_data, p_reason,
        p_expected_draft_version, p_rule_version
    )
    returning * into created_snapshot;

    update private.career_profiles
       set confirmed_data = p_confirmed_data,
           active_snapshot_id = created_snapshot.id,
           rule_version = p_rule_version,
           updated_at = now()
     where id = locked_profile.id;

    return next created_snapshot;
end;
$$;

revoke all on function private.confirm_career_profile(
    uuid, integer, jsonb, text, text
) from public, anon, authenticated;
grant execute on function private.confirm_career_profile(
    uuid, integer, jsonb, text, text
) to service_role;

-- A profilverzió aktiválása külön, auditálható GPS-esemény.
alter table private.career_gps_events
    drop constraint if exists career_gps_events_esemeny_tipus_check;
alter table private.career_gps_events
    add constraint career_gps_events_esemeny_tipus_check check (
        esemeny_tipus in (
            'profile_draft_created', 'profile_fact_confirmed',
            'profile_snapshot_activated', 'career_goal_selected',
            'career_intent_confirmed', 'market_snapshot_ready',
            'job_shortlist_created', 'application_package_approved',
            'transition_path_selected', 'training_selected',
            'foreign_shortlist_created', 'portfolio_preview_ready',
            'portfolio_published'
        )
    );

