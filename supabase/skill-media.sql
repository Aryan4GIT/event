-- ===========================================================================
--  Skill media — artists post one photo or short video of themselves working
--  Run once in the SQL Editor, after phase2.sql.
--
--  Until this runs, the registration form still works: it only sends the
--  clip when the column exists, and silently skips it when it does not.
-- ===========================================================================

-- 1. Where the clip lives ---------------------------------------------------
alter table public.vendors
  add column if not exists skill_path text;      -- storage URL, same shape as photo_path

comment on column public.vendors.skill_path is
  'One photo or short video of the artist working. Private bucket while pending, public once approved.';

-- 2. The pending bucket must accept video, and a bigger file ----------------
--    40 MB covers a 30-second phone clip; anything longer belongs on Instagram.
update storage.buckets
   set file_size_limit    = 41943040,
       allowed_mime_types = array[
         'image/jpeg','image/png','image/webp',
         'video/mp4','video/webm','video/quicktime'
       ]
 where id = 'vendor-pending';

update storage.buckets
   set allowed_mime_types = array[
         'image/jpeg','image/png','image/webp',
         'video/mp4','video/webm','video/quicktime'
       ]
 where id = 'vendor-photos';

-- 3. Show it on the public roster -------------------------------------------
--    Still no phone numbers or emails: one extra safe column, nothing else.
create or replace view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.skill_path, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved';

grant select on public.roster to anon, authenticated;

-- 4. Check ------------------------------------------------------------------
select column_name
from information_schema.columns
where table_schema = 'public' and table_name = 'vendors' and column_name = 'skill_path';

select id, file_size_limit, allowed_mime_types
from storage.buckets
where id in ('vendor-pending','vendor-photos');
