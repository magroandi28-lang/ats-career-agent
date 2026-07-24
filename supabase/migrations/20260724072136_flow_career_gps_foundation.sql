-- Flow és Career GPS alap
-- Ez a migráció a 02-flow-career-gps.md tervben rögzített öt táblát hozza
-- létre: flow_sessions, flow_messages, career_gps_events, career_gps_snapshots,
-- active_tasks. Mind a `private` sémában, ugyanazzal a védelmi mintával, mint
-- a platform_security_foundation migráció (csak service_role éri el, a
-- böngésző/authenticated soha közvetlenül -- Flow a FastAPI backend
-- végpontjain keresztül kommunikál ezekkel).

create table private.flow_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  allapot text not null default 'aktiv'
    check (allapot in ('aktiv', 'szunetel', 'lezart')),
  aktiv_cel text,
  letrehozva timestamptz not null default now(),
  utolso_aktivitas timestamptz not null default now()
);

create table private.flow_messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references private.flow_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  szerep text not null check (szerep in ('user', 'flow')),
  tartalom text not null,
  strukturalt_hivatkozasok jsonb not null default '[]'::jsonb,
  letrehozva timestamptz not null default now()
);

create table private.career_gps_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid references private.flow_sessions(id) on delete set null,
  esemeny_tipus text not null check (esemeny_tipus in (
    'profile_draft_created',
    'profile_fact_confirmed',
    'career_goal_selected',
    'market_snapshot_ready',
    'job_shortlist_created',
    'application_package_approved',
    'transition_path_selected',
    'training_selected',
    'foreign_shortlist_created',
    'portfolio_preview_ready',
    'portfolio_published'
  )),
  payload jsonb not null default '{}'::jsonb,
  szabalyverzio text not null,
  actor text not null check (actor in ('user', 'flow', 'agent', 'system')),
  letrehozva timestamptz not null default now()
);

create table private.career_gps_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  terulet text not null check (terulet in (
    'profil', 'karriercel', 'piaci_kep', 'felkeszultseg',
    'palyazas', 'portfolio', 'specialis_ut'
  )),
  allapot text not null check (allapot in (
    'nincs', 'vazlat', 'ellenorzendo', 'megerositett',
    'nyitott', 'kivalasztott', 'validalt',
    'betoltve', 'elavult',
    'hianyok', 'terv', 'folyamatban', 'megfelelo',
    'nincs_shortlist', 'shortlist', 'anyag_kesz', 'beadas_kovetese',
    'tartalom_keszul', 'elonezet', 'publikalt',
    'aktiv', 'inaktiv'
  )),
  utolso_esemeny_id uuid references private.career_gps_events(id) on delete set null,
  frissitve timestamptz not null default now(),
  unique (user_id, terulet)
);

create table private.active_tasks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  feladat_tipus text not null check (char_length(feladat_tipus) between 1 and 100),
  allapot text not null default 'futo'
    check (allapot in ('futo', 'johagyasra_var', 'hibas', 'kesz')),
  kapcsolt_agent_run_id uuid references private.agent_runs(id) on delete set null,
  kapcsolt_approval_id uuid references private.approval_requests(id) on delete set null,
  letrehozva timestamptz not null default now(),
  frissitve timestamptz not null default now()
);

create index flow_sessions_user_aktivitas_idx
  on private.flow_sessions (user_id, utolso_aktivitas desc);
create index flow_messages_session_idx
  on private.flow_messages (session_id, letrehozva);
create index flow_messages_user_idx
  on private.flow_messages (user_id, letrehozva desc);
create index career_gps_events_user_idx
  on private.career_gps_events (user_id, letrehozva desc);
create index career_gps_events_session_idx
  on private.career_gps_events (session_id, letrehozva)
  where session_id is not null;
create index career_gps_snapshots_user_idx
  on private.career_gps_snapshots (user_id, terulet);
create index active_tasks_user_allapot_idx
  on private.active_tasks (user_id, allapot, letrehozva desc);

-- Ugyanaz a zárolási minta, mint a platform_security_foundation migrációban:
-- csak a service_role (a FastAPI backend) éri el, a böngésző/authenticated
-- kliens közvetlenül soha.
revoke all on private.flow_sessions from public, anon, authenticated;
revoke all on private.flow_messages from public, anon, authenticated;
revoke all on private.career_gps_events from public, anon, authenticated;
revoke all on private.career_gps_snapshots from public, anon, authenticated;
revoke all on private.active_tasks from public, anon, authenticated;

grant select, insert, update, delete on private.flow_sessions to service_role;
grant select, insert, update, delete on private.flow_messages to service_role;
grant select, insert, update, delete on private.career_gps_events to service_role;
grant select, insert, update, delete on private.career_gps_snapshots to service_role;
grant select, insert, update, delete on private.active_tasks to service_role;

-- Defense in depth: RLS bekapcsolva, policy nélkül -- a service_role úgyis
-- megkerüli az RLS-t, az anon/authenticated pedig már a grant szinten sincs
-- feljogosítva, ez egy plusz védelmi réteg, ha valaha grant-hiba történne.
alter table private.flow_sessions enable row level security;
alter table private.flow_messages enable row level security;
alter table private.career_gps_events enable row level security;
alter table private.career_gps_snapshots enable row level security;
alter table private.active_tasks enable row level security;
