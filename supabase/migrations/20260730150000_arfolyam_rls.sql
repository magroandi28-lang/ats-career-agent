-- Az árfolyamot kizárólag a backend használja béradatok egységesítéséhez.
-- A public séma miatt ettől még kötelező a többrétegű védelem: a böngészős
-- szerepkörök ne érhessék el akkor sem, ha később véletlenül szélesebb
-- alapértelmezett jogosultság kerülne a sémára.

alter table public.arfolyam enable row level security;
alter table public.arfolyam force row level security;

revoke all on table public.arfolyam from public, anon, authenticated;
grant select, insert, update, delete on table public.arfolyam to service_role;
