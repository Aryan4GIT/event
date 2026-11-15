-- ===========================================================================
--  Artists who manage their own profile are listed first
--  Run once in the SQL Editor, after youtube-on-profiles.sql. Safe to re-run.
--
--  roster.js puts an artist who has claimed their profile ahead of the others
--  in the same category. The public view gains only a yes/no for that, as its
--  last column: the login id itself stays private. Until this is run the
--  website keeps the staff order it has today.
-- ===========================================================================

-- Same view as youtube-on-profiles.sql, plus claimed.
create or replace view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.skill_path, v.media, v.bio, v.languages,
         v.performance_duration, v.sort,
         public.youtube_ids(v.links) as youtube,
         (v.user_id is not null) as claimed
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'artist';

grant select on public.roster to anon, authenticated;

-- Check: how many listed artists manage their own profile, per category
select category_key, count(*) filter (where claimed) as self_managed, count(*) as listed
from public.roster group by category_key order by category_key;
