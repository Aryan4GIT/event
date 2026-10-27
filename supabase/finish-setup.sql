-- ===========================================================================
--  Finish setup — run after schema.sql and seed-roster.sql
--
--  BEFORE RUNNING: create your login first.
--    Dashboard → Authentication → Users → Add user
--    → your email + a password → Create user
--  Then change the email on the marked line below to that same email.
-- ===========================================================================

-- 1. Make yourself an admin (matches by email, so nothing to copy and paste)
insert into public.staff (user_id)
select id
from auth.users
where email = 'aryansingh73321@gmail.com'      -- <<< your login email
on conflict (user_id) do nothing;

-- 2. Belt and braces: take the public role off the vendors and staff tables.
--    Row level security already returns nothing to the public, but with the
--    privilege removed as well, a future policy mistake still cannot leak a
--    phone number. The public reads the roster view and nothing else.
revoke all on public.vendors from anon;
revoke all on public.staff   from anon;

-- 3. Check it worked — should print your email, and 102 for the roster.
select u.email as admin_email
from public.staff s join auth.users u on u.id = s.user_id;

select count(*) as live_roster_rows from public.roster;
