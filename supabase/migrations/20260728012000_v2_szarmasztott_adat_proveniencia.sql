-- Hiteles adatbázis V2: a kinyert készség- és tételsorok csak pontos,
-- ellenőrizhető snapshot-provenance mellett számíthatnak hitelesnek.
-- A meglévő legacy sorok változatlanul megmaradnak, új provenance-t nem
-- kapnak, ezért későbbi snapshot sem emelheti be őket az elemzésekbe.

alter table public.hirdetes_tetel
    add column if not exists snapshot_id bigint
        references public.hirdetes_snapshot(id) on delete restrict,
    add column if not exists feldolgozo_verzio text,
    add column if not exists forras_bizonyitek text,
    add column if not exists forras_bizonyitek_kezdete integer,
    add column if not exists forras_bizonyitek_vege integer;

alter table public.hirdetes_keszseg
    add column if not exists id bigint generated always as identity,
    add column if not exists snapshot_id bigint
        references public.hirdetes_snapshot(id) on delete restrict,
    add column if not exists feldolgozo_verzio text,
    add column if not exists forras_bizonyitek text,
    add column if not exists forras_bizonyitek_kezdete integer,
    add column if not exists forras_bizonyitek_vege integer;

-- A NOT VALID megőrzi az esetleges korábbi snapshotokat, de minden új EURES
-- "teljes" sort már a forrásséma és a description pontos egyezése véd.
alter table public.hirdetes_snapshot
    add constraint hirdetes_snapshot_eures_teljes_forras_check check (
        forras_tipus <> 'eures'
        or szoveg_minoseg <> 'teljes'
        or (
            jsonb_typeof(raw_payload) = 'object'
            and jsonb_typeof(raw_payload -> 'id') in ('string', 'number')
            and length(btrim(raw_payload ->> 'id')) > 0
            and jsonb_typeof(raw_payload -> 'title') = 'string'
            and length(btrim(raw_payload ->> 'title')) > 0
            and jsonb_typeof(raw_payload -> 'description') = 'string'
            and length(btrim(raw_payload ->> 'description')) > 0
            and forras_szoveg_mezo = 'description'
            and raw_szoveg = raw_payload ->> 'description'
            and forras_azonosito = raw_payload ->> 'id'
            and (
                not (raw_payload ? 'employer')
                or jsonb_typeof(raw_payload -> 'employer') = 'object'
            )
            and (
                not (raw_payload ? 'locationMap')
                or jsonb_typeof(raw_payload -> 'locationMap') = 'object'
            )
            and (
                not (raw_payload ? 'availableLanguages')
                or jsonb_typeof(
                    raw_payload -> 'availableLanguages'
                ) = 'array'
            )
            and (
                not (raw_payload ? 'positionScheduleCodes')
                or jsonb_typeof(
                    raw_payload -> 'positionScheduleCodes'
                ) = 'array'
            )
        )
    ) not valid;

-- A korábbi összetett PK megakadályozná, hogy egy legacy kapcsolat mellett
-- ugyanaz a készség már bizonyítható V2 sorként is létrejöhessen.
alter table public.hirdetes_keszseg
    drop constraint if exists hirdetes_keszseg_pkey;
alter table public.hirdetes_keszseg
    alter column id set not null;
alter table public.hirdetes_keszseg
    add constraint hirdetes_keszseg_pkey primary key (id);

drop index if exists public.hirdetes_tetel_egyedi;
create unique index if not exists hirdetes_tetel_v2_egyedi
    on public.hirdetes_tetel(snapshot_id, szekcio, normalizalt)
    where snapshot_id is not null;
create unique index if not exists hirdetes_tetel_legacy_egyedi
    on public.hirdetes_tetel(hirdetes_id, szekcio, normalizalt)
    where snapshot_id is null;

create unique index if not exists hirdetes_keszseg_v2_egyedi
    on public.hirdetes_keszseg(snapshot_id, keszseg_id)
    where snapshot_id is not null;
create unique index if not exists hirdetes_keszseg_legacy_egyedi
    on public.hirdetes_keszseg(hirdetes_id, keszseg_id)
    where snapshot_id is null;

alter table public.hirdetes_tetel
    add constraint hirdetes_tetel_v2_proveniencia_check check (
        (
            snapshot_id is null
            and feldolgozo_verzio is null
            and forras_bizonyitek is null
            and forras_bizonyitek_kezdete is null
            and forras_bizonyitek_vege is null
        )
        or (
            snapshot_id is not null
            and length(btrim(feldolgozo_verzio)) > 0
            and length(forras_bizonyitek) > 0
            and forras_bizonyitek_kezdete >= 0
            and forras_bizonyitek_vege > forras_bizonyitek_kezdete
        )
    );

alter table public.hirdetes_keszseg
    add constraint hirdetes_keszseg_v2_proveniencia_check check (
        (
            snapshot_id is null
            and feldolgozo_verzio is null
            and forras_bizonyitek is null
            and forras_bizonyitek_kezdete is null
            and forras_bizonyitek_vege is null
        )
        or (
            snapshot_id is not null
            and length(btrim(feldolgozo_verzio)) > 0
            and length(forras_bizonyitek) > 0
            and forras_bizonyitek_kezdete >= 0
            and forras_bizonyitek_vege > forras_bizonyitek_kezdete
        )
    );

create or replace function private.hirdetes_szarmasztott_v2_ved()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
declare
    snapshot_hirdetes_id bigint;
    snapshot_raw_szoveg text;
    snapshot_elemzesre_alkalmas boolean;
    snapshot_begyujtve timestamptz;
begin
    if tg_op <> 'INSERT' then
        raise exception
            'A kinyert hirdetesadat append-only; modositas es torles tilos.'
            using errcode = '23514';
    end if;

    if new.snapshot_id is null then
        raise exception
            'Uj kinyert sorhoz snapshot_id es pontos proveniencia kotelezo.'
            using errcode = '23514';
    end if;

    select
        hirdetes_id,
        raw_szoveg,
        elemzesre_alkalmas,
        begyujtve
    into
        snapshot_hirdetes_id,
        snapshot_raw_szoveg,
        snapshot_elemzesre_alkalmas,
        snapshot_begyujtve
    from public.hirdetes_snapshot
    where id = new.snapshot_id;

    if not found
        or snapshot_hirdetes_id is distinct from new.hirdetes_id
        or snapshot_elemzesre_alkalmas is not true then
        raise exception
            'A kinyert sor snapshotja nem alkalmas vagy masik hirdetese.'
            using errcode = '23514';
    end if;

    if exists (
        select 1
        from public.hirdetes_snapshot frissebb
        where frissebb.hirdetes_id = new.hirdetes_id
          and (
              frissebb.begyujtve > snapshot_begyujtve
              or (
                  frissebb.begyujtve = snapshot_begyujtve
                  and frissebb.id > new.snapshot_id
              )
          )
    ) then
        raise exception
            'Kinyert sor csak a hirdetes legujabb snapshotjabol keszulhet.'
            using errcode = '23514';
    end if;

    if substring(
        snapshot_raw_szoveg
        from new.forras_bizonyitek_kezdete + 1
        for new.forras_bizonyitek_vege
            - new.forras_bizonyitek_kezdete
    ) is distinct from new.forras_bizonyitek then
        raise exception
            'A forrasbizonyitek nem egyezik a snapshot pontos szeletevel.'
            using errcode = '23514';
    end if;

    return new;
end;
$$;

drop trigger if exists hirdetes_tetel_v2_ved
    on public.hirdetes_tetel;
create trigger hirdetes_tetel_v2_ved
before insert or update or delete on public.hirdetes_tetel
for each row execute function private.hirdetes_szarmasztott_v2_ved();

drop trigger if exists hirdetes_keszseg_v2_ved
    on public.hirdetes_keszseg;
create trigger hirdetes_keszseg_v2_ved
before insert or update or delete on public.hirdetes_keszseg
for each row execute function private.hirdetes_szarmasztott_v2_ved();

revoke all on function private.hirdetes_szarmasztott_v2_ved()
    from public, anon, authenticated, service_role;

-- A snapshot hirdetéskapcsolata adatbázis-szinten is csak egyszer,
-- NULL-ról tölthető ki. A nyers és auditmezők továbbra is immutábilisak.
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
    if old.hirdetes_id is not null
        and new.hirdetes_id is distinct from old.hirdetes_id then
        raise exception
            'A hirdetes_snapshot hirdetes_id csak egyszer, NULL-rol toltheto.'
            using errcode = '23514';
    end if;
    return new;
end;
$$;

comment on column public.hirdetes_tetel.snapshot_id is
    'A tétel pontos forrássnapshotja; NULL csak migráció előtti legacy sornál maradhat.';
comment on column public.hirdetes_keszseg.snapshot_id is
    'A készségkapcsolat pontos forrássnapshotja; NULL csak migráció előtti legacy sornál maradhat.';
comment on column public.hirdetes_tetel.forras_bizonyitek is
    'A snapshot raw_szoveg mezőjének változatlan, pontos szelete.';
comment on column public.hirdetes_keszseg.forras_bizonyitek is
    'A snapshot raw_szoveg mezőjének változatlan, pontos szelete.';

grant usage, select on sequence public.hirdetes_keszseg_id_seq
    to service_role;
