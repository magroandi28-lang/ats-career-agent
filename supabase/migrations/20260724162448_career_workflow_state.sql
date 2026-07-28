-- Utólag mentve az éles migrációs naplóból (20260724162448).
-- A migráció lefutott az adatbázison, de fájl nem tartozott hozzá.

-- Determinisztikus karrierfolyamat-állapot.
-- A kliens és az LLM nem írhatja közvetlenül; csak a backend service role.

create table if not exists private.career_workflows (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    session_id uuid references private.flow_sessions(id) on delete set null,
    current_state text not null default 'CEL_TISZTAZATLAN',
    intent text,
    context jsonb not null default '{}'::jsonb,
    rule_version text not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint career_workflows_state_check check (current_state in (
        'CEL_TISZTAZATLAN', 'CEL_TISZTAZOTT', 'PROFIL_HIANYOS',
        'PROFIL_ELLENORZOTT', 'TANACSADAS_AKTIV', 'PIACI_KEP_KESZ',
        'CV_TERVEZET', 'CV_JOVAHAGYOTT', 'ALLASKERESES_AKTIV',
        'ALLASOK_BEMUTATVA', 'ALLAS_KIVALASZTVA', 'HIRDETES_ELLENORZOTT',
        'ATS_KESZ', 'PALYAZATI_CSOMAG_TERVEZET', 'KULDESRE_JOVAHAGYVA',
        'PALYAZAS_ELINDITVA', 'PALYAZAS_BEADVA_NAPLOZVA'
    )),
    constraint career_workflows_intent_check check (intent is null or intent in (
        'cv_ellenorzes', 'cv_frissites', 'cv_keszites', 'allas_kereses',
        'konkret_palyazas', 'tanacsadas', 'palyavaltas', 'piaci_korkep',
        'kepzes_kereses', 'portfolio', 'bizonytalan'
    )),
    constraint career_workflows_status_check check (
        status in ('active', 'completed', 'cancelled')
    ),
    constraint career_workflows_context_object_check check (
        jsonb_typeof(context) = 'object'
    )
);

create unique index if not exists career_workflows_one_active_per_user
    on private.career_workflows(user_id)
    where status = 'active';

create index if not exists career_workflows_user_updated_idx
    on private.career_workflows(user_id, updated_at desc);

-- A már létező append-only GPS napló zárt eseménytípus-listáját bővítjük.
alter table private.career_gps_events
    drop constraint if exists career_gps_events_esemeny_tipus_check;
alter table private.career_gps_events
    add constraint career_gps_events_esemeny_tipus_check check (
        esemeny_tipus in (
            'profile_draft_created', 'profile_fact_confirmed',
            'career_goal_selected', 'career_intent_confirmed',
            'market_snapshot_ready', 'job_shortlist_created',
            'application_package_approved', 'transition_path_selected',
            'training_selected', 'foreign_shortlist_created',
            'portfolio_preview_ready', 'portfolio_published'
        )
    );

alter table private.career_workflows enable row level security;
alter table private.career_workflows force row level security;

revoke all on table private.career_workflows from public, anon, authenticated;
grant all on table private.career_workflows to service_role;

