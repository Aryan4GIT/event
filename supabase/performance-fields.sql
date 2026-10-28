-- ===========================================================================
--  Performance duration — how long an artist actually performs for
--  Run once in the SQL Editor, after skill-media.sql.
--
--  Until this runs, the registration form still works: it retries the insert
--  without the column rather than turning the artist away.
--
--  Nothing here is needed for "where you are based" (already the city column)
--  or the YouTube link (already the links column, now labelled YouTube-only).
-- ===========================================================================

alter table public.vendors
  add column if not exists performance_duration text;

comment on column public.vendors.performance_duration is
  'Free text, as the artist typed it: "45 minutes", "2 hours", "3 sets of 20 min".';

-- Keep the public letterbox honest: a registration may set it, within reason.
-- Recreating the policy is how every other migration here changes one.
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
    and char_length(coalesce(performance_duration, '')) <= 80
    and char_length(coalesce(links, '')) <= 300
  );

-- Not added to public.roster: duration is a booking detail we quote on, not
-- something the public roster shows. Add it there if that ever changes.

-- Check ---------------------------------------------------------------------
select column_name
from information_schema.columns
where table_schema = 'public' and table_name = 'vendors'
  and column_name = 'performance_duration';
