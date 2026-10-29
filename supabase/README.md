# Roster backend — Phase 1 setup

Everything here is written and tested. These are the steps only you can do,
because they need an account in your name. About ten minutes.

Until step 4 is done the website behaves exactly as it does now: the roster
reads `artists-data.js` and nothing breaks.

---

## 1. Create the project

[supabase.com](https://supabase.com) → sign up (GitHub or email) → **New project**.

- **Name:** `showmaqers`
- **Region:** `South Asia (Mumbai)` — closest to your visitors
- **Database password:** let it generate one and save it somewhere safe. You
  will not need it for the website, but you cannot recover it later.
- **Plan:** Free

The project takes a minute or two to come up.

## 2. Create the tables

Left sidebar → **SQL Editor** → **New query**. Paste all of
[`schema.sql`](schema.sql) and press **Run**.

It should finish with "Success. No rows returned."

## 3. Load the 102 artists

New query again. Paste all of [`seed-roster.sql`](seed-roster.sql) and **Run**.

The last statement prints a count per category. Check it reads:
`anchors 88`, `dj 9`, `singers 5`.

## 4. Connect the website

**Project Settings** (gear icon) → **Data API**. Copy two values:

| Supabase calls it | Looks like |
|---|---|
| Project URL | `https://abcdefgh.supabase.co` |
| anon / public key | a long `eyJ…` string |

Paste both into **`supabase-config.js`** in the website folder, replacing the
`YOUR-…` placeholders. Reload `manpower.html` — the roster now comes from the
database. It will look identical, because it is the same 102 artists.

> The anon key is meant to be public. It can only reach the `roster` view,
> which has no phone numbers or emails in it. Never copy the **service_role**
> key into any website file.

## 5. Make yourself the admin

Needed for Phase 3, worth doing now.

1. **Authentication** → **Users** → **Add user** → your email and a password.
2. Open [`finish-setup.sql`](finish-setup.sql), change the one email line to
   that same email, and run the whole file in the SQL Editor.

It matches your login by email, so there is no UID to copy. It also revokes
the public role's leftover privileges on `vendors` and `staff`, and prints a
check at the end: your email, and `102`.

## 6. Stop the project going to sleep

Free projects pause after **7 days with no API traffic**, and someone has to
wake them by hand in the dashboard. Any real visitor traffic prevents this. To
be safe, set up a free daily ping at [cron-job.org](https://cron-job.org) to:

```
https://YOUR-PROJECT-REF.supabase.co/rest/v1/roster?select=id&limit=1
```

with the header `apikey: YOUR-ANON-KEY`. If the site ever goes quiet for a
week, this keeps the roster live.

---

## Phase 2 — registrations go into the database

Run [`phase2.sql`](phase2.sql) in the SQL Editor. That is the only step.

After it, the form on `vendors.html` saves straight to the database: no
account, no login, no WhatsApp round trip. The artist fills it in, adds a
photo, and lands on a "registration received" screen. If the database is ever
unreachable the form falls back to a pre-filled WhatsApp message, so nobody is
turned away.

The public can **write** a registration and **nothing else** — it cannot read
the queue back, not even its own row.

### Where new registrations appear

Until the Phase 3 dashboard exists, read them in Supabase:

**Table Editor → `vendors`** → filter `status` = `pending`.

Their photo is in the `vendor-pending` bucket under **Storage**; the row's
`photo_path` says which folder.

---

## Skill media — a photo or video of the artist working

Run [`skill-media.sql`](skill-media.sql) in the SQL Editor. One step again.

It adds a `skill_path` column, lets the upload buckets accept video up to
40 MB, and adds that one column to the public `roster` view.

After it, the registration form has a second, optional upload: one photo or
short video of the artist at a real event. It appears under their photo on the
admin dashboard, so you can watch it before deciding. Approving publishes the
clip along with the photo, and their roster card gets a **▶ Reel** badge that
plays the clip full screen.

Until this file is run the form still works — it just sends the registration
without the clip rather than failing.

---

## Performance duration

Run [`performance-fields.sql`](performance-fields.sql) in the SQL Editor.

It adds a `performance_duration` column and lets a public registration set it.
The form now asks three things it did not before:

| On the form | Where it lands |
|---|---|
| **Where you are based** (city and area, required) | the existing `city` column |
| **How long you perform** (required) | the new `performance_duration` column |
| **YouTube link of your performance** (optional) | the existing `links` column |

Instagram links are no longer asked for, and the form rejects one if pasted.

Until this file is run the form still works — it retries the registration
without the duration rather than failing.

---

## Artist details from the live site

Run [`artist-details.sql`](artist-details.sql) in the SQL Editor.

It adds an `event_type` column and fills in, for the 102 legacy artists, what
showmaqers.com states under each of them: location, performance duration,
budget and event type. The anchors page gives all four; the DJ and singer
pages give a location only, so those rows get a city and nothing else.

The file is generated — re-run `python tools/pull-artist-details.py` after the
live site changes rather than editing it. That script also refreshes
`artists-data.js`, which is where the website itself reads the details, and it
stops with an error if the live page and the roster have drifted out of step.

None of these four reach the public roster view: a visitor sees a name, a
category and a photo, and budget stays between you and the client.

---

## What is in the database

| Table | What it holds |
|---|---|
| `categories` | the 20 roster sections |
| `vendors` | one row per artist — contact details, status, photo, skill clip |
| `staff` | who is allowed to approve |
| `roster` *(view)* | the only thing the public can read: approved artists, safe columns |

Two rules are enforced by the database itself, not by the pages:

1. **Phone numbers and emails never leave the server.** The public has no
   access to `vendors` at all, only to the `roster` view.
2. **No artist can approve themselves.** Only rows in `staff` may change a
   vendor's status, enforced by a trigger.

## If the roster ever looks empty

The page falls back to `artists-data.js` whenever the database is unreachable,
returns an error, or returns nothing — so visitors keep seeing the roster. If
the live data stops arriving, check in this order:

1. Is the project paused? (dashboard shows it)
2. Did step 4's URL/key get pasted correctly?
3. Run `select count(*) from public.roster;` — if it is 0, re-run `seed-roster.sql`.
4. From **30 Oct 2026** Supabase requires explicit table grants. They are in
   `schema.sql` section 6; re-running that section fixes a silent empty result.
