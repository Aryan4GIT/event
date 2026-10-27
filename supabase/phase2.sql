-- ===========================================================================
--  Phase 2 — let artists register without making an account
--  Run once in the SQL Editor, after finish-setup.sql.
--
--  The public gets a letterbox: it may post one pending registration and
--  upload one photo. It still cannot read anything back — not its own row,
--  not anyone else's. Only you, in the dashboard, can read the queue.
-- ===========================================================================

-- "Other" needs somewhere to land. It has no section on the roster page, so
-- an artist filed here stays invisible until you recategorise them.
insert into public.categories (key, label, sort)
values ('other','Other',99)
on conflict (key) do nothing;

-- 1. The public may insert a registration, and only a registration ----------
grant insert on public.vendors to anon;

drop policy if exists "public may register" on public.vendors;
create policy "public may register"
  on public.vendors for insert to anon
  with check (
    status      = 'pending'          -- cannot arrive pre-approved
    and user_id is null
    and source  = 'self'
    and consent_at is not null       -- they ticked the box
    and char_length(name) between 2 and 80
    and char_length(coalesce(bio, '')) <= 2000
    and char_length(coalesce(phone, '')) <= 30
    and char_length(coalesce(city, '')) <= 80
  );

-- 2. The public may drop a photo in the private bucket ----------------------
--    Insert only: it cannot list, read back or overwrite what is in there.
drop policy if exists "public may upload a photo" on storage.objects;
create policy "public may upload a photo"
  on storage.objects for insert to anon
  with check (bucket_id = 'vendor-pending');

-- Hard limits so the bucket cannot be filled with junk: 5 MB, images only.
update storage.buckets
   set file_size_limit    = 5242880,
       allowed_mime_types = array['image/jpeg','image/png','image/webp']
 where id = 'vendor-pending';

-- 3. Check: should print 0 rows now, and your registrations later -----------
select count(*) as pending_registrations
from public.vendors
where status = 'pending';
