-- ===========================================================================
--  Live band, comedian and mimicry roles, and four photos + two videos
--  Run once in the SQL Editor, after registration-safety.sql. Safe to re-run.
--
--  Run this BEFORE publishing the website that offers the new roles: until
--  the categories exist, a registration that ticks only one of them fails the
--  categories foreign key, and one with more than three samples fails the
--  policy below.
-- ===========================================================================

-- 1. Three more artist roles --------------------------------------------------
insert into public.categories (key, label, sort) values
  ('live-band', 'Live Band',       25),
  ('comedian',  'Comedians',       26),
  ('mimicry',   'Mimicry Artists', 27)
on conflict (key) do update set label = excluded.label, sort = excluded.sort;

-- 2. Two approved artists who had to pick "Other" before these roles existed --
update public.vendors set category_key = 'live-band', roles = array['live-band']
  where id = 'b9efceda-cd55-4675-a630-eeaea1434962' and category_key = 'other';   -- Azaadi The Band
update public.vendors set category_key = 'comedian', roles = array['comedian','mimicry']
  where id = '248ed7c0-993e-4ae3-a795-3c124cecd540' and category_key = 'other';   -- Comedian Chirag Wadhwani

-- 3. The public letterbox takes four photos and two videos -------------------
--    Same policy as registration-safety.sql, with six samples instead of three.
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
    and coalesce(array_length(media, 1), 0) <= 6
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

-- 4. Check: three rows, then the two artists in their new roles ---------------
select key, label from public.categories where key in ('live-band','comedian','mimicry')
union all
select category_key, name from public.vendors
  where id in ('b9efceda-cd55-4675-a630-eeaea1434962','248ed7c0-993e-4ae3-a795-3c124cecd540');
