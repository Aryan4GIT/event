-- ===========================================================================
--  Join us — artists pick more than one role, and vendors register too
--  Run once in the SQL Editor, after performance-fields.sql. Safe to re-run.
--
--  Until this runs, the registration form still works: it retries the insert
--  without the new columns rather than turning anyone away. New roles will
--  fail the categories foreign key until the inserts below land, though.
-- ===========================================================================

-- 1. Four more artist roles -------------------------------------------------
insert into public.categories (key, label, sort) values
  ('choreographer', 'Choreographer',           21),
  ('sfx',           'SFX / Special Effects Artist', 22),
  ('mehendi',       'Mehendi Artist',          23),
  ('makeup-artist', 'Make-up Artist',          24)
on conflict (key) do update set label = excluded.label, sort = excluded.sort;

-- 2. Vendor services. Prefixed v- so nothing can confuse a supplier with an
--    artist, and so the roster view can be filtered on kind alone.
insert into public.categories (key, label, sort) values
  ('v-decor',        'Decorator — balloon, flower, theme',      101),
  ('v-stage',        'Stage, fabrication & printing',           102),
  ('v-tent',         'Tent, pandal & German hangar',            103),
  ('v-furniture',    'Furniture & props on rent',               104),
  ('v-sound',        'Sound, light & LED screens',              105),
  ('v-games',        'Games, rides & inflatables on rent',      106),
  ('v-catering',     'Catering, food stalls & carts',           107),
  ('v-bakery',       'Bakery & cakes',                          108),
  ('v-florist',      'Florist & flower supply',                 109),
  ('v-cooling',      'AC, cooler, fan & generator on rent',     110),
  ('v-transport',    'Transport & logistics',                   111),
  ('v-venue',        'Venue, farmhouse & banquet',              112),
  ('v-manpower',     'Manpower, bouncers & security',           113),
  ('v-photo-studio', 'Photo & video studio, 360° booth',        114),
  ('v-invites',      'Invites, gifting & favours',              115),
  ('v-other',        'Other supplier',                          199)
on conflict (key) do update set label = excluded.label, sort = excluded.sort;

-- 3. Two columns on vendors -------------------------------------------------
--    kind  : keeps suppliers out of the artist roster
--    roles : every role they ticked. category_key stays the primary one, so
--            the roster, the admin queue and manpower.html keep working as is.
alter table public.vendors
  add column if not exists kind       text not null default 'artist',
  add column if not exists roles      text[],
  add column if not exists skill_path text;   -- skill-media.sql adds this too; both are idempotent

do $$ begin
  alter table public.vendors add constraint vendors_kind_check
    check (kind in ('artist','vendor'));
exception when duplicate_object then null; end $$;

comment on column public.vendors.kind is
  'artist = performer or wardrobe, listed on the roster. vendor = supplier, never listed.';
comment on column public.vendors.roles is
  'Every category key the registrant ticked, primary first. category_key mirrors roles[1].';

create index if not exists vendors_kind_idx on public.vendors (kind, status);

-- Existing rows are all artists; the default already says so, this is for clarity.
update public.vendors set kind = 'artist' where kind is null;

-- 4. The public letterbox, widened by exactly these two columns -------------
drop policy if exists "public may register" on public.vendors;
create policy "public may register"
  on public.vendors for insert to anon
  with check (
    status      = 'pending'          -- cannot arrive pre-approved
    and user_id is null
    and source  = 'self'
    and consent_at is not null       -- they ticked the box
    and kind in ('artist','vendor')
    and coalesce(array_length(roles, 1), 1) between 1 and 8
    and char_length(name) between 2 and 80
    and char_length(coalesce(bio, '')) <= 2000
    and char_length(coalesce(phone, '')) <= 30
    and char_length(coalesce(city, '')) <= 80
    and char_length(coalesce(performance_duration, '')) <= 80
    and char_length(coalesce(links, '')) <= 300
  );

-- 5. The public roster is artists only --------------------------------------
--    Dropped first, not replaced: skill_path sits before sort, and CREATE OR
--    REPLACE VIEW cannot insert a column in the middle.
drop view if exists public.roster;
create view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.skill_path, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'artist';

grant select on public.roster to anon, authenticated;
