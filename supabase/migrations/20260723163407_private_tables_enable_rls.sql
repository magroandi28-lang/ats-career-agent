-- Defense in depth for backend-only operational tables.
-- No anon/authenticated policies are created; the backend service role remains available.

alter table private.background_jobs enable row level security;
alter table private.approval_requests enable row level security;
alter table private.agent_runs enable row level security;
alter table private.audit_events enable row level security;
