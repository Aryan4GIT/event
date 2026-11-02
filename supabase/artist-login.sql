-- ===========================================================================
--  Artist self-service — invite, claim, and edit your own profile
--  Run once in the SQL Editor, after media-gallery.sql. Safe to re-run.
--
--  Staff invite an artist from admin.html, which mints a one-time token. The
--  artist opens claim.html?t=<token>, signs up, and the row is linked to their
--  login. From then on they edit their own profile at my-profile.html.
--
--  Two rules the whole thing exists to keep:
--    1. An artist can never publish to the public roster unreviewed. Their
--       name, city, fee and the like go live; their bio, photo and gallery
--       land in drafts that staff approve.
--    2. A visitor must never get a direct line to the artist. The public views
--       carry no phone and no email, and the guard below refuses a phone
--       number typed into any field that does reach the public.
-- ===========================================================================

-- 1. The invite --------------------------------------------------------------
alter table public.vendors
  add column if not exists claim_token      text,
  add column if not exists claim_expires_at timestamptz;

create unique index if not exists vendors_claim_token_idx
  on public.vendors (claim_token) where claim_token is not null;

comment on column public.vendors.claim_token is
  'One-time invite secret, minted by staff and sent to the artist. Cleared the moment it is used.';

-- 2. What an artist proposes, pending review ---------------------------------
alter table public.vendors
  add column if not exists bio_draft   text,
  add column if not exists photo_draft text,
  add column if not exists media_draft text[],
  add column if not exists draft_at    timestamptz;

comment on column public.vendors.bio_draft is
  'Artist-submitted bio awaiting staff approval. Never read by the public views.';

create index if not exists vendors_draft_idx on public.vendors (draft_at)
  where draft_at is not null;

-- 3. Does this text contain something that looks like a phone number? --------
--    Commas are deliberately NOT separators, so a fee of 1,50,000 reads as
--    short runs while 98117 88643 and +91 98117 88643 both read as one long
--    one. Eight digits, because real fees reach seven.
create or replace function public.looks_like_a_phone(txt text)
returns boolean language sql immutable as $$
  select exists (
    select 1
    from regexp_matches(coalesce(txt, ''), '([0-9][0-9 ().+-]{5,}[0-9])', 'g') as m
    where length(regexp_replace(m[1], '[^0-9]', '', 'g')) >= 8
  );
$$;

-- 4. Claiming a profile ------------------------------------------------------
--    security definer: the caller may not read vendors, and must not be able
--    to fish for valid tokens. Returns the row id on success.
create or replace function public.claim_profile(token text)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_id uuid;
begin
  if auth.uid() is null then
    raise exception 'sign in first';
  end if;

  -- the guard below would see user_id still null and refuse the very update
  -- that sets it, so say plainly that this is a claim. Transaction-local, so
  -- it cannot leak into any other statement.
  perform set_config('app.claiming', 'on', true);

  update public.vendors
     set user_id          = auth.uid(),
         claim_token      = null,
         claim_expires_at = null
   where claim_token = token
     and claim_expires_at > now()
     and user_id is null
     and status = 'approved'
  returning id into v_id;

  if v_id is null then
    raise exception 'that invite link is not valid any more';
  end if;
  return v_id;
end $$;

revoke all on function public.claim_profile(text) from public, anon;
grant execute on function public.claim_profile(text) to authenticated;

-- 5. The guard ---------------------------------------------------------------
--    Runs only for an artist editing through the API. Staff and direct SQL
--    pass straight through; the existing review guard still pins approval.
create or replace function public.guard_artist_self_edit()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null or public.is_staff() then return new; end if;
  if current_setting('app.claiming', true) = 'on' then return new; end if;
  if old.user_id is null or old.user_id is distinct from auth.uid() then
    raise exception 'you may only edit your own profile';
  end if;

  -- an artist decides none of these
  new.id               := old.id;
  new.user_id          := old.user_id;
  new.status           := old.status;
  new.kind             := old.kind;
  new.category_key     := old.category_key;
  new.roles            := old.roles;
  new.sort             := old.sort;
  new.source           := old.source;
  new.claim_token      := old.claim_token;
  new.claim_expires_at := old.claim_expires_at;

  -- the published bio and gallery move only when staff approve a draft
  new.bio        := old.bio;
  new.photo_path := old.photo_path;
  new.media      := old.media;
  new.skill_path := old.skill_path;

  -- no direct line to the artist, in anything that reaches a visitor
  if public.looks_like_a_phone(new.name)
     or public.looks_like_a_phone(new.city)
     or public.looks_like_a_phone(new.fee_note)
     or public.looks_like_a_phone(new.languages)
     or public.looks_like_a_phone(new.performance_duration)
     or public.looks_like_a_phone(new.bio_draft) then
    raise exception 'please leave phone numbers out — clients reach you through Showmaqers';
  end if;

  -- the link is a showreel, not a way to be messaged
  if coalesce(new.links, '') <> ''
     and new.links !~* '^(https?://)?(www\.)?(youtube\.com/|youtu\.be/|m\.youtube\.com/)' then
    raise exception 'the link must be a YouTube URL';
  end if;

  new.draft_at := case
    when new.bio_draft is distinct from old.bio_draft
      or new.photo_draft is distinct from old.photo_draft
      or new.media_draft is distinct from old.media_draft
    then now() else old.draft_at end;

  return new;
end $$;

drop trigger if exists vendors_guard_self_edit on public.vendors;
create trigger vendors_guard_self_edit
  before update on public.vendors
  for each row execute function public.guard_artist_self_edit();

-- 6. An artist reads and writes their own row --------------------------------
--    schema.sql created these; they are restated because a later migration
--    replaced the storage half with staff-only policies.
drop policy if exists "read own row" on public.vendors;
create policy "read own row"
  on public.vendors for select to authenticated
  using (user_id = auth.uid() or public.is_staff());

drop policy if exists "update own row" on public.vendors;
create policy "update own row"
  on public.vendors for update to authenticated
  using (user_id = auth.uid() or public.is_staff())
  with check (user_id = auth.uid() or public.is_staff());

-- 7. An artist uploads into a folder named after their own login -------------
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

-- 8. The public gains the approved bio, and nothing else ---------------------
--    Still no phone, no email, no drafts.
drop view if exists public.roster;
create view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.skill_path, v.media, v.bio, v.languages,
         v.performance_duration, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'artist';

drop view if exists public.supplier;   -- bio goes before sort, which replace cannot do
create view public.supplier as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.media, v.bio, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'vendor';

grant select on public.roster   to anon, authenticated;
grant select on public.supplier to anon, authenticated;
