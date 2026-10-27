-- ===========================================================================
--  Approving fails with "could not publish the photo"? Run this.
--
--  Publishing copies the photo into the public bucket, which needs a storage
--  policy that lets a staff login write there. This re-creates all four
--  storage policies from scratch, then shows you what exists.
-- ===========================================================================

-- 1. What is actually in place right now (read this before and after) -------
select policyname, cmd, roles::text as applies_to
from pg_policies
where schemaname = 'storage' and tablename = 'objects'
order by policyname;

-- 2. Re-create the four policies -------------------------------------------
drop policy if exists "artist uploads own folder"  on storage.objects;
drop policy if exists "artist reads own folder"    on storage.objects;
drop policy if exists "artist removes own folder"  on storage.objects;
drop policy if exists "staff publish photo"        on storage.objects;
drop policy if exists "staff unpublish photo"      on storage.objects;
drop policy if exists "public may upload a photo"  on storage.objects;

-- the public drops a registration photo into the private bucket
create policy "public may upload a photo"
  on storage.objects for insert to anon, authenticated
  with check (bucket_id = 'vendor-pending');

-- staff read the private bucket to review, and clear it afterwards
create policy "staff reads pending"
  on storage.objects for select to authenticated
  using (bucket_id = 'vendor-pending' and public.is_staff());

create policy "staff removes pending"
  on storage.objects for delete to authenticated
  using (bucket_id = 'vendor-pending' and public.is_staff());

-- staff publish an approved photo to the public bucket, and can replace it
create policy "staff publish photo"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'vendor-photos' and public.is_staff());

create policy "staff replace photo"
  on storage.objects for update to authenticated
  using (bucket_id = 'vendor-photos' and public.is_staff())
  with check (bucket_id = 'vendor-photos' and public.is_staff());

create policy "staff unpublish photo"
  on storage.objects for delete to authenticated
  using (bucket_id = 'vendor-photos' and public.is_staff());

-- 3. Confirm your login is seen as staff (must print true) -----------------
--    Run this while signed in to the SQL editor it will say false — that is
--    expected there. The real check is the dashboard working afterwards.
select exists (select 1 from public.staff) as staff_row_exists;

-- 4. The policies now in place ---------------------------------------------
select policyname, cmd, roles::text as applies_to
from pg_policies
where schemaname = 'storage' and tablename = 'objects'
order by policyname;
