-- ===========================================================================
--  Work samples — artists and vendors show photos and a short video
--  Run once in the SQL Editor, after join-us.sql. Safe to re-run.
--
--  Two photos and one video of at most 10 seconds, per registrant. The browser
--  re-encodes all three before upload (WebP 1600px, 720p video), so a full
--  gallery costs roughly 1.5 MB rather than the 40 MB raw phone footage would.
--
--  One text[] rather than a media table: three rows per artist does not earn
--  a join, an FK, its own RLS and its own view. The file extension says
--  whether a path is a photo or a video, which is what the page already keys
--  on for the reel badge.
-- ===========================================================================

-- 1. Where the gallery lives ------------------------------------------------
alter table public.vendors
  add column if not exists media text[];

comment on column public.vendors.media is
  'Ordered work samples: storage paths. Private bucket while pending, copied to the public one on approval. .mp4/.webm/.mov are videos, the rest photos. photo_path stays the headshot the roster card shows.';

-- 2. The public letterbox accepts a gallery, within reason ------------------
--    Six paths, because the form allows four photos and two videos.
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
    and coalesce(array_length(media, 1), 0) <= 6   -- four photos and two videos
    and char_length(name) between 2 and 80
    and char_length(coalesce(bio, '')) <= 2000
    and char_length(coalesce(phone, '')) <= 30
    and char_length(coalesce(city, '')) <= 80
    and char_length(coalesce(performance_duration, '')) <= 80
    and char_length(coalesce(links, '')) <= 300
  );

-- 3. The pending bucket must take video ------------------------------------
--    It was still images-only at 5 MB, which is why the "show us your skill"
--    clip has been failing silently. 12 MB is ample for a re-encoded 10s clip
--    and still refuses raw 4K footage outright.
update storage.buckets
   set file_size_limit    = 12582912,
       allowed_mime_types = array[
         'image/jpeg','image/png','image/webp',
         'video/mp4','video/webm','video/quicktime'
       ]
 where id = 'vendor-pending';

update storage.buckets
   set file_size_limit    = 12582912,
       allowed_mime_types = array[
         'image/jpeg','image/png','image/webp',
         'video/mp4','video/webm','video/quicktime'
       ]
 where id = 'vendor-photos';

-- 4. The public roster carries the gallery ---------------------------------
--    Still no phone numbers or emails: one more safe column, nothing else.
drop view if exists public.roster;
create view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.skill_path, v.media, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'artist';

grant select on public.roster to anon, authenticated;

-- 5. Vendors are suppliers, not roster artists, but their samples are still
--    public on their own profile. A second view keeps them out of the roster
--    while letting a profile page read one by id.
create or replace view public.supplier as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.media, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'vendor';

grant select on public.supplier to anon, authenticated;
