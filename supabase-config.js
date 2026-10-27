/* Supabase connection for the live artist roster.
   Fill both values from your project: Dashboard → Project Settings → Data API.

   Both are safe to ship in public page source. The anon key is a public
   identifier, not a secret — row level security in supabase/schema.sql decides
   what it can reach, which is the roster view and nothing else. Never put the
   service_role key in any file the browser downloads.

   While these say YOUR-… the site falls back to artists-data.js, so the roster
   keeps working exactly as it does today. */
window.SUPABASE = {
  url:     'https://opjxxwxkasrzpukjhkvy.supabase.co',
  anonKey: 'sb_publishable_OkCzttKq--CStmAuopVUew_H0yq82-a'
};
