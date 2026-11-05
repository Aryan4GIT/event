-- ===========================================================================
--  Vendor directory: a vendor is listed under every category they ticked
--  Run once in the SQL Editor, after artist-login.sql. Safe to re-run.
--
--  The vendors page and profiles work without this, placing each vendor under
--  their first category only. This does two more things:
--    1. adds roles to the public supplier view, so a decorator who is also a
--       florist appears in both sections. Still no phone and no email.
--    2. raises the upload cap from 12 MB to 30 MB. The browser shrinks a clip
--       to about 2 MB when it can, so this only matters when a phone cannot
--       convert one and the original has to be sent as it is.
-- ===========================================================================

-- 1. The public view gains the categories ------------------------------------
--    Dropped first, not replaced: roles goes before sort, which replace cannot do.
drop view if exists public.supplier;
create view public.supplier as
  select v.id, v.name, v.category_key, c.label as category_label, v.roles,
         v.city, v.photo_path, v.media, v.bio, v.sort
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'vendor';

grant select on public.supplier to anon, authenticated;

-- 2. Both buckets, because approving copies a file from one to the other -----
update storage.buckets
   set file_size_limit = 31457280
 where id in ('vendor-pending', 'vendor-photos');

-- 3. Check: the approved vendors, and the new limit ---------------------------
select count(*) as approved_vendors from public.supplier;
select id, file_size_limit from storage.buckets where id in ('vendor-pending', 'vendor-photos');
