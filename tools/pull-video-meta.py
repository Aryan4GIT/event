#!/usr/bin/env python
"""Fetch the real title, upload date and length of every YouTube video the
pages embed, into video-meta.json.

  python tools/pull-video-meta.py

Why this exists
---------------
Each embedded video is described to search engines as a VideoObject, and
Google will not use one without an uploadDate and a thumbnail. The first
build filled both in with placeholders -- the same 2024-01-01 for every
video and the logo as the thumbnail -- which is worse than leaving them out:
a date that is wrong for 90 videos out of 90 is a claim about the page that
is simply false. YouTube has the real values on each watch page, so this
reads them once and keeps them, and tools/seo-pass.py builds the VideoObject
from what is here. A video this could not read gets no VideoObject at all.

Already-fetched videos are kept, so a re-run only asks about new ones.
"""

import glob
import html
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "video-meta.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; showmaqers-site-rebuild/1.0)",
      "Accept-Language": "en"}
EMBED = re.compile(r'<iframe[^>]+src="[^"]*youtube(?:-nocookie)?\.com/embed/([\w-]{11})')


def embedded_ids():
    ids = set()
    for path in glob.glob(os.path.join(ROOT, "*.html")) + glob.glob(os.path.join(ROOT, "blog", "*.html")):
        ids.update(EMBED.findall(open(path, encoding="utf-8").read()))
    return sorted(ids)


def meta(page, attr, name):
    m = re.search(r'<meta %s="%s" content="([^"]*)"' % (attr, re.escape(name)), page)
    return html.unescape(m.group(1)).strip() if m else None


def iso_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return "PT" + ("%dH" % h if h else "") + ("%dM" % m if m else "") + "%dS" % s


def fetch(vid):
    r = requests.get("https://www.youtube.com/watch?v=" + vid, headers=UA, timeout=30)
    r.raise_for_status()
    page = r.text
    uploaded = meta(page, "itemprop", "uploadDate")
    if not uploaded:                      # removed, private, or a consent wall
        return None
    length = re.search(r'"lengthSeconds":"(\d+)"', page)
    return {
        "title": meta(page, "name", "title"),
        "description": meta(page, "name", "description"),
        "uploadDate": uploaded,
        "duration": iso_duration(length.group(1)) if length else None,
    }


def main():
    known = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = [v for v in embedded_ids() if v not in known]
    for n, vid in enumerate(todo, 1):
        try:
            got = fetch(vid)
        except requests.RequestException as e:
            print("  %s: %s" % (vid, e))
            continue
        if got:
            known[vid] = got
        print("%3d/%d %s %s" % (n, len(todo), vid, (got or {}).get("uploadDate") or "-- no date"))
        time.sleep(0.4)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(known.items())), f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("video-meta.json: %d videos" % len(known))


if __name__ == "__main__":
    sys.exit(main())
