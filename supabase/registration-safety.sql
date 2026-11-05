-- ===========================================================================
--  Registration photo, and closing what a stranger could slip into a row
--  Run once in the SQL Editor, after vendor-directory.sql. Safe to re-run.
--
--  Publish the website first. An older copy of the vendor form sends no photo,
--  so once this has run it can only offer its WhatsApp fallback.
--
--  What this changes:
--    1. A public registration must carry a photo, for vendors as for artists.
--    2. A public registration can set only the fields the forms send. Until now
--       a hand-written request could set an invite token, a sort position,
--       drafts, or a file path aimed at another bucket or another Supabase
--       service, which admin.html then opened using the admin's login.
--    3. Logged-in accounts can no longer create rows. Sign-up is open, and
--       nothing on the site needs this door.
--    4. Saving a profile checks only the fields that changed. A vendor who
--       registered with an Instagram link, or a price written as 20000-50000,
--       could not save anything at all, uploads included.
--    5. A profile's drafts must point at that login's own uploads.
--    6. The public vendor view stops carrying the "Contact: <person>" line.
-- ===========================================================================

-- 1. What one of our private uploads looks like -------------------------------
--    Matches isPendingPath in media-upload.js. Keep the two the same.
create or replace function public.pending_path_ok(p text)
returns boolean language sql immutable as $$
  select coalesce(p ~ '^vendor-pending(/[A-Za-z0-9_.-]+)+$' and p !~ '\.\.', false);
$$;

grant execute on function public.pending_path_ok(text) to anon, authenticated;

-- 2. The public letterbox -----------------------------------------------------
--    Named columns, so anything the forms do not send is refused outright.
revoke all on public.vendors from anon;
grant insert (name, category_key, roles, kind, city, phone, email, years_experience,
              fee_note, languages, links, performance_duration, bio, photo_path,
              media, status, source, consent_at)
  on public.vendors to anon;

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
    and coalesce(array_length(media, 1), 0) <= 3
    and public.pending_path_ok(photo_path)   -- required, and null fails this
    and not exists (select 1 from unnest(media) as m where not public.pending_path_ok(m))
    and char_length(name) between 2 and 80
    and char_length(coalesce(bio, '')) <= 2000
    and char_length(coalesce(phone, '')) <= 30
    and char_length(coalesce(email, '')) <= 254
    and char_length(coalesce(city, '')) <= 80
    and char_length(coalesce(fee_note, '')) <= 200
    and char_length(coalesce(languages, '')) <= 200
    and char_length(coalesce(performance_duration, '')) <= 80
    and char_length(coalesce(links, '')) <= 300
  );

-- 3. The other way in ---------------------------------------------------------
drop policy if exists "create own row" on public.vendors;
revoke insert on public.vendors from authenticated;

-- 4. Saving a profile ---------------------------------------------------------
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

  -- no direct line to the artist, in anything that reaches a visitor. Only what
  -- changed: an old value must not stop them saving something else.
  if (new.name is distinct from old.name and public.looks_like_a_phone(new.name))
     or (new.city is distinct from old.city and public.looks_like_a_phone(new.city))
     or (new.fee_note is distinct from old.fee_note and public.looks_like_a_phone(new.fee_note))
     or (new.languages is distinct from old.languages and public.looks_like_a_phone(new.languages))
     or (new.performance_duration is distinct from old.performance_duration and public.looks_like_a_phone(new.performance_duration))
     or (new.bio_draft is distinct from old.bio_draft and public.looks_like_a_phone(new.bio_draft)) then
    raise exception 'please leave phone numbers out — clients reach you through Showmaqers';
  end if;

  -- an artist's link is a showreel. A vendor's form asks for a website or
  -- Instagram, and this column never reaches a visitor.
  if new.kind = 'artist'
     and new.links is distinct from old.links
     and coalesce(new.links, '') <> ''
     and new.links !~* '^(https?://)?(www\.)?(youtube\.com/|youtu\.be/|m\.youtube\.com/)' then
    raise exception 'the link must be a YouTube URL';
  end if;

  -- staff open these files when they review, so they must be this login's own
  if new.photo_draft is distinct from old.photo_draft
     and new.photo_draft is not null
     and not (public.pending_path_ok(new.photo_draft)
              and new.photo_draft like 'vendor-pending/' || auth.uid() || '/%') then
    raise exception 'that photo is not one you uploaded';
  end if;
  if new.media_draft is distinct from old.media_draft
     and exists (select 1 from unnest(new.media_draft) as m
                 where not (public.pending_path_ok(m)
                            and m like 'vendor-pending/' || auth.uid() || '/%')) then
    raise exception 'that file is not one you uploaded';
  end if;

  new.draft_at := case
    when new.bio_draft is distinct from old.bio_draft
      or new.photo_draft is distinct from old.photo_draft
      or new.media_draft is distinct from old.media_draft
    then now() else old.draft_at end;

  return new;
end $$;

-- 5. A login uploads into its own folder --------------------------------------
--    Restated because fix-storage.sql drops it. Without it, or the wider policy
--    fix-storage.sql adds, uploads from my-profile.html are refused.
drop policy if exists "artist uploads own folder" on storage.objects;
create policy "artist uploads own folder"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'vendor-pending'
              and (storage.foldername(name))[1] = auth.uid()::text);

-- 6. The public vendor view ---------------------------------------------------
create or replace view public.supplier as
  select v.id, v.name, v.category_key, c.label as category_label, v.roles,
         v.city, v.photo_path, v.media,
         regexp_replace(v.bio, '^Contact:[^\n]*\n*', '') as bio, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'vendor';

grant select on public.supplier to anon, authenticated;

-- 7. Check. The editor shows only the last result, so it is all one row -------
--    The first two should read 0, and the third is the number to look at: any
--    row counted there holds a file path that did not come from our forms, and
--    admin.html will refuse to open it. Reject those rows.
select
  (select count(*) from information_schema.column_privileges
    where grantee = 'anon' and table_name = 'vendors' and column_name = 'claim_token') as anon_can_set_invites,
  (select count(*) from pg_policies
    where tablename = 'vendors' and policyname = 'create own row') as logins_can_create_rows,
  (select count(*) from public.vendors v
    where exists (select 1
                  from unnest(array[v.photo_path, v.skill_path, v.photo_draft]
                              || coalesce(v.media, '{}') || coalesce(v.media_draft, '{}')) as p
                  where p is not null
                    and not public.pending_path_ok(p)
                    and p !~ '^images/'
                    and p !~ '^https://[a-z0-9]+\.supabase\.co/storage/v1/object/public/vendor-photos/')
  ) as rows_with_odd_paths,
  (select count(*) from public.vendors
    where kind = 'vendor' and status in ('pending', 'approved') and photo_path is null) as vendors_without_a_photo;
