-- ===========================================================================
--  Dhol player and digital caricature artist roles
--  Run once in the SQL Editor. Safe to re-run.
--
--  Run this BEFORE publishing the website that offers these roles: the artist
--  form saves the first ticked role as category_key, so until the category
--  exists a registration that ticks one of them first fails the categories
--  foreign key.
-- ===========================================================================

insert into public.categories (key, label, sort) values
  ('dhol',               'Dhol Players',               28),
  ('digital-caricature', 'Digital Caricature Artists', 29)
on conflict (key) do update set label = excluded.label, sort = excluded.sort;

-- Check: two rows
select key, label, sort from public.categories where key in ('dhol', 'digital-caricature');
