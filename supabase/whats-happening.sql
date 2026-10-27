-- ===========================================================================
--  What state are the two registrations in? Read-only, one query.
--  (The SQL editor only shows the LAST result, so keep this on its own.)
-- ===========================================================================

select name,
       status,
       category_key,
       left(coalesce(photo_path, '—'), 60) as photo,
       reviewed_at
from public.vendors
where source = 'self'
order by created_at desc;
