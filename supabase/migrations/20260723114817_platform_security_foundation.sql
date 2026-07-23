-- Platform–adat–biztonság alap
-- A böngésző kizárólag az üres, explicit `api` sémát láthatja.
-- Az alkalmazás a meglévő katalógust a backend titkos kulcsával éri el.

create schema if not exists api;
create schema if not exists private;
create schema if not exists extensions;

-- A projekt vector 0.8.2 bővítménye áthelyezhető; ne a Data API alapértelmezett
-- public sémájában lakjon.
alter extension vector set schema extensions;

revoke all on schema private from public, anon, authenticated;
grant usage on schema private to service_role;
revoke all on schema extensions from anon, authenticated;
grant usage on schema extensions to service_role;

grant usage on schema api to anon, authenticated, service_role;

-- A jelenlegi publikus katalógust nem tesszük közvetlenül böngészhetővé.
-- Későbbi kliensoldali olvasáshoz külön, minimális api nézet és grant kell.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on functions from anon, authenticated;

alter default privileges for role postgres in schema api
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema api
  revoke all on functions from anon, authenticated;

create table private.background_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  job_type text not null check (char_length(job_type) between 1 and 100),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  input_ref jsonb not null default '{}'::jsonb,
  result_ref jsonb not null default '{}'::jsonb,
  error_code text,
  attempt_count integer not null default 0
    check (attempt_count between 0 and 20),
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default now()
);

create table private.approval_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  action_type text not null check (char_length(action_type) between 1 and 100),
  action_payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'expired', 'executed')),
  expires_at timestamptz not null,
  decided_at timestamptz,
  executed_at timestamptz,
  created_at timestamptz not null default now()
);

create table private.agent_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  parent_run_id uuid references private.agent_runs(id) on delete set null,
  agent_name text not null check (char_length(agent_name) between 1 and 100),
  status text not null default 'running'
    check (status in ('running', 'succeeded', 'failed', 'cancelled')),
  tool_names text[] not null default '{}',
  input_fingerprint text,
  output_fingerprint text,
  policy_decisions jsonb not null default '[]'::jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table private.audit_events (
  id bigint generated always as identity primary key,
  occurred_at timestamptz not null default now(),
  request_id text,
  user_id uuid references auth.users(id) on delete set null,
  actor_type text not null
    check (actor_type in ('user', 'flow', 'agent', 'system', 'admin')),
  event_type text not null check (char_length(event_type) between 1 and 120),
  resource_type text,
  resource_id text,
  outcome text not null check (outcome in ('allowed', 'denied', 'succeeded', 'failed')),
  metadata jsonb not null default '{}'::jsonb
);

create index background_jobs_user_created_idx
  on private.background_jobs (user_id, created_at desc);
create index background_jobs_status_created_idx
  on private.background_jobs (status, created_at);
create index approval_requests_user_status_idx
  on private.approval_requests (user_id, status, created_at desc);
create index agent_runs_user_created_idx
  on private.agent_runs (user_id, created_at desc);
create index audit_events_user_time_idx
  on private.audit_events (user_id, occurred_at desc);
create index audit_events_request_idx
  on private.audit_events (request_id)
  where request_id is not null;

revoke all on all tables in schema private from public, anon, authenticated;
revoke all on all sequences in schema private from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema private to service_role;
grant usage, select on all sequences in schema private to service_role;

alter default privileges for role postgres in schema private
  revoke all on tables from public, anon, authenticated;
alter default privileges for role postgres in schema private
  grant select, insert, update, delete on tables to service_role;
alter default privileges for role postgres in schema private
  grant usage, select on sequences to service_role;

-- A biztonsági ellenőrzés által jelzett változtatható search_path javítása.
alter function public.tudas_kereses(extensions.vector, integer)
  set search_path = pg_catalog, public, extensions;
revoke all on function public.tudas_kereses(extensions.vector, integer)
  from public, anon, authenticated;
grant execute on function public.tudas_kereses(extensions.vector, integer)
  to service_role;
