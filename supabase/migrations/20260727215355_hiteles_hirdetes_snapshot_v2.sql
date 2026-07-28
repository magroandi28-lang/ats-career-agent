-- Hiteles hirdetés-adatfolyam V2: változatlan forráselem és determinisztikus
-- minőségkapu. Ez belső audit-réteg, nem publikus alkalmazásadat.

create table if not exists public.hirdetes_snapshot (
    id bigint generated always as identity primary key,
    hirdetes_id bigint
        references public.hirdetesek(id) on delete set null,
    forras_tipus text not null,
    forras_azonosito text not null,
    forras_url text,
    keresesi_kulcsszo text,
    forras_szoveg_mezo text not null,
    raw_payload jsonb,
    raw_szoveg text not null,
    raw_payload_sha256 text not null,
    raw_szoveg_sha256 text not null,
    nyelv text not null default 'ismeretlen',
    szoveg_minoseg text not null,
    validacios_allapot text not null,
    listazasra_alkalmas boolean not null default false,
    elemzesre_alkalmas boolean not null default false,
    validacios_hibak text[] not null default '{}',
    figyelmeztetesek text[] not null default '{}',
    gyujto_verzio text not null,
    gyujtesi_futas text not null,
    szabalyverzio text not null,
    begyujtve timestamptz not null default now(),

    constraint hirdetes_snapshot_forras_tipus_check check (
        forras_tipus in ('portal', 'ceges', 'jooble', 'eures', 'egyeb')
    ),
    constraint hirdetes_snapshot_forras_azonosito_check check (
        length(btrim(forras_azonosito)) > 0
    ),
    constraint hirdetes_snapshot_szoveg_mezo_check check (
        length(btrim(forras_szoveg_mezo)) > 0
    ),
    constraint hirdetes_snapshot_payload_hash_check check (
        raw_payload_sha256 ~ '^[0-9a-f]{64}$'
    ),
    constraint hirdetes_snapshot_szoveg_hash_check check (
        raw_szoveg_sha256 ~ '^[0-9a-f]{64}$'
    ),
    constraint hirdetes_snapshot_nyelv_check check (
        length(btrim(nyelv)) between 2 and 32
    ),
    constraint hirdetes_snapshot_minoseg_check check (
        szoveg_minoseg in ('teljes', 'reszleges', 'snippet', 'ismeretlen')
    ),
    constraint hirdetes_snapshot_validacio_check check (
        validacios_allapot in ('elfogadott', 'karanten')
    ),
    constraint hirdetes_snapshot_elfogadott_check check (
        validacios_allapot <> 'elfogadott'
        or (
            listazasra_alkalmas
            and cardinality(validacios_hibak) = 0
            and jsonb_typeof(raw_payload) = 'object'
        )
    ),
    constraint hirdetes_snapshot_elemzes_check check (
        not elemzesre_alkalmas
        or (
            validacios_allapot = 'elfogadott'
            and listazasra_alkalmas
            and szoveg_minoseg = 'teljes'
        )
    )
);

create unique index if not exists hirdetes_snapshot_tartalom_egyedi
    on public.hirdetes_snapshot (
        forras_tipus,
        forras_azonosito,
        raw_payload_sha256
    );

create index if not exists hirdetes_snapshot_hirdetes_id_idx
    on public.hirdetes_snapshot(hirdetes_id);

create index if not exists hirdetes_snapshot_forras_ido_idx
    on public.hirdetes_snapshot(forras_tipus, begyujtve desc);

create index if not exists hirdetes_snapshot_elemzesre_idx
    on public.hirdetes_snapshot(forras_tipus, begyujtve desc)
    where elemzesre_alkalmas;

comment on table public.hirdetes_snapshot is
    'Belső, újraszámolás-álló audit-réteg: nyers forráselem, hashek és determinisztikus minőségkapu.';
comment on column public.hirdetes_snapshot.raw_payload is
    'A forrásból kapott egyedi hirdetéselem átalakítás nélküli JSON-tartalma.';
comment on column public.hirdetes_snapshot.raw_szoveg is
    'A forrás eredeti, elemzésre kijelölt szövegmezője tisztítás és rövidítés nélkül.';
comment on column public.hirdetes_snapshot.elemzesre_alkalmas is
    'Csak teljes, validált szövegnél igaz; ATS és karrierút kizárólag ezt használhatja.';

alter table public.hirdetes_snapshot enable row level security;
alter table public.hirdetes_snapshot force row level security;

revoke all on table public.hirdetes_snapshot
    from public, anon, authenticated;
revoke all on sequence public.hirdetes_snapshot_id_seq
    from public, anon, authenticated;

grant select, insert, update on table public.hirdetes_snapshot
    to service_role;
grant usage, select on sequence public.hirdetes_snapshot_id_seq
    to service_role;
