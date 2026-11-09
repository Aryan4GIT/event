-- ===========================================================================
--  YouTube videos on artist profiles
--  Run once in the SQL Editor, after artist-login.sql. Safe to re-run.
--
--  artist.html shows a thumbnail for each YouTube video in an artist's link
--  field. The public view gains only the 11-character video ids pulled out of
--  that field, never the field itself: a website, Instagram handle or phone
--  number typed there stays private, as before. Channel links (@name) carry no
--  video, so they show nothing.
-- ===========================================================================

-- 1. Video ids out of free text ----------------------------------------------
create or replace function public.youtube_ids(links text)
returns text[] language sql immutable as $$
  select array(
    select r.m[1]
    from regexp_matches(coalesce(links, ''),
      '(?:youtube\.com/(?:watch\?(?:[^\s&]*&)*v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})',
      'gi') as r(m))
$$;
grant execute on function public.youtube_ids(text) to anon, authenticated;

-- 2. The roster gains them, as its last column -------------------------------
--    Same view as artist-login.sql section 8, plus youtube.
create or replace view public.roster as
  select v.id, v.name, v.category_key, c.label as category_label,
         v.city, v.photo_path, v.skill_path, v.media, v.bio, v.languages,
         v.performance_duration, v.sort,
         public.youtube_ids(v.links) as youtube
  from public.vendors v
  join public.categories c on c.key = v.category_key
  where v.status = 'approved' and v.kind = 'artist';

grant select on public.roster to anon, authenticated;

-- 3. Check: the first row must read {dQw4w9WgXcQ,abcDEF_12-x}, then every
--    listed artist who has a video ----------------------------------------------
select public.youtube_ids('https://youtu.be/dQw4w9WgXcQ, m.youtube.com/watch?feature=share&v=abcDEF_12-x '
                          'and youtube.com/@somechannel')::text as youtube
union all
select name || ': ' || youtube::text from public.roster where cardinality(youtube) > 0;
