-- ===========================================================================
--  SHOWMAQERS — artist roster backend, Phase 1
--  Run once in the Supabase dashboard → SQL Editor → New query → Run.
--  Safe to run again: it drops and recreates policies rather than failing.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Categories — these keys match the section ids in manpower.html
-- ---------------------------------------------------------------------------
create table if not exists public.categories (
  key   text primary key,
  label text not null,
  sort  int  not null default 0
);

insert into public.categories (key, label, sort) values
  ('dj',                'DJ',                          1),
  ('anchors',           'Male & Female Emcee Anchors', 2),
  ('singers',           'Singers',                     3),
  ('dancers',           'Dancers',                     4),
  ('photographer',      'Photographer',                5),
  ('videographer',      'Videographer',                6),
  ('tattoo',            'Tattoo Artist',               7),
  ('face-painter',      'Face Painter',                8),
  ('game-coordinator',  'Game Coordinator',            9),
  ('russian-promoters', 'Russian Promoters',          10),
  ('parlour',           'Parlour Beautician',         11),
  ('nail-artist',       'Nail Artist',                12),
  ('tarot',             'Tarot Card Reader',          13),
  ('pottery',           'Pottery Maker',              14),
  ('puppet',            'Puppet Show Performers',     15),
  ('magician',          'Magician',                   16),
  ('stilt-walker',      'Stilt Walker (longman)',     17),
  ('joker',             'Joker / Clown / Charlie',    18),
  ('juggler',           'Juggler',                    19),
  ('mascots',           'Mascots',                    20)
on conflict (key) do update set label = excluded.label, sort = excluded.sort;

-- ---------------------------------------------------------------------------
-- 2. Vendors — one row per artist
-- ---------------------------------------------------------------------------
do $$ begin
  create type public.vendor_status as enum ('pending','approved','rejected','unlisted');
exception when duplicate_object then null; end $$;

create table if not exists public.vendors (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid references auth.users on delete set null,
  name             text not null,
  category_key     text not null references public.categories(key),
  city             text,
  phone            text,
  email            text,
  years_experience int check (years_experience between 0 and 70),
  fee_note         text,
  languages        text,
  links            text,
  bio              text,
  photo_path       text,          -- storage URL, or a legacy "images/…" path
  status           public.vendor_status not null default 'pending',
  sort             int not null default 0,
  source           text not null default 'self',   -- 'self' | 'legacy' | 'admin'
  consent_at       timestamptz,
  created_at       timestamptz not null default now(),
  reviewed_at      timestamptz,
  reviewed_by      uuid references auth.users,
  review_note      text           -- internal only, never exposed publicly
);

create index if not exists vendors_live_idx on public.vendors (status, category_key, sort);
create index if not exists vendors_user_idx on public.vendors (user_id);

-- ---------------------------------------------------------------------------
-- 3. Staff — whoever may approve. Add yourself in step 4 of the README.
-- ---------------------------------------------------------------------------
create table if not exists public.staff (
  user_id uuid primary key references auth.users on delete cascade,
  role    text not null default 'admin' check (role in ('admin'))
);

-- security definer so it can read staff even while staff has RLS on
create or replace function public.is_staff()
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.staff s where s.user_id = auth.uid());
$$;

-- ---------------------------------------------------------------------------
-- 4. Row level security — default deny, then open the smallest doors
-- ---------------------------------------------------------------------------
alter table public.categories enable row level security;
alter table public.vendors    enable row level security;
alter table public.staff      enable row level security;

drop policy if exists "categories are reference data" on public.categories;
create policy "categories are reference data"
  on public.categories for select to anon, authenticated using (true);

-- an artist reads and edits only their own row; staff read everything
drop policy if exists "read own row" on public.vendors;
create policy "read own row"
  on public.vendors for select to authenticated
  using (user_id = auth.uid() or public.is_staff());

drop policy if exists "create own row" on public.vendors;
create policy "create own row"
  on public.vendors for insert to authenticated
  with check (user_id = auth.uid() and status = 'pending');

drop policy if exists "update own row" on public.vendors;
create policy "update own row"
  on public.vendors for update to authenticated
  using (user_id = auth.uid() or public.is_staff())
  with check (user_id = auth.uid() or public.is_staff());

drop policy if exists "staff may delete" on public.vendors;
create policy "staff may delete"
  on public.vendors for delete to authenticated using (public.is_staff());

drop policy if exists "staff may read staff" on public.staff;
create policy "staff may read staff"
  on public.staff for select to authenticated using (public.is_staff());

-- An artist must never be able to approve themselves. RLS lets them update
-- their own row, so this trigger pins the review columns unless staff did it.
create or replace function public.guard_vendor_review()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then return new; end if;     -- direct SQL / service role
  if public.is_staff() then return new; end if;
  if new.status is distinct from old.status then
    raise exception 'only staff may change approval status';
  end if;
  new.reviewed_at := old.reviewed_at;
  new.reviewed_by := old.reviewed_by;
  new.review_note := old.review_note;
  new.source      := old.source;
  return new;
end $$;

drop trigger if exists vendors_guard_review on public.vendors;
create trigger vendors_guard_review
  before update on public.vendors
  for each row execute function public.guard_vendor_review();

-- ---------------------------------------------------------------------------
-- 5. The only thing the public may read
--    A plain view, so it runs as its owner and bypasses RLS on vendors. That
--    is the point: it exposes approved rows and safe columns only — no phone,
--    no email, no review notes. anon gets no privileges on vendors itself.
-- ---------------------------------------------------------------------------
create or replace view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved';

-- ---------------------------------------------------------------------------
-- 6. Grants. Required: from 30 Oct 2026 Supabase no longer grants these
--    automatically, and without them the API returns nothing.
-- ---------------------------------------------------------------------------
grant usage  on schema public             to anon, authenticated;
grant select on public.roster             to anon, authenticated;
grant select on public.categories         to anon, authenticated;
grant select, insert, update on public.vendors to authenticated;
grant select on public.staff              to authenticated;
-- anon deliberately gets nothing on public.vendors

-- ---------------------------------------------------------------------------
-- 7. Photo buckets (used from Phase 2; created now so nothing changes later)
--    vendor-pending : private, what artists upload
--    vendor-photos  : public, what approval copies across
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('vendor-pending','vendor-pending', false),
       ('vendor-photos','vendor-photos',  true)
on conflict (id) do nothing;

drop policy if exists "artist uploads own folder" on storage.objects;
create policy "artist uploads own folder"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'vendor-pending'
              and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "artist reads own folder" on storage.objects;
create policy "artist reads own folder"
  on storage.objects for select to authenticated
  using (bucket_id = 'vendor-pending'
         and ((storage.foldername(name))[1] = auth.uid()::text or public.is_staff()));

drop policy if exists "artist removes own folder" on storage.objects;
create policy "artist removes own folder"
  on storage.objects for delete to authenticated
  using (bucket_id = 'vendor-pending'
         and ((storage.foldername(name))[1] = auth.uid()::text or public.is_staff()));

drop policy if exists "staff publish photo" on storage.objects;
create policy "staff publish photo"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'vendor-photos' and public.is_staff());

drop policy if exists "staff unpublish photo" on storage.objects;
create policy "staff unpublish photo"
  on storage.objects for delete to authenticated
  using (bucket_id = 'vendor-photos' and public.is_staff());
