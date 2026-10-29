#!/usr/bin/env python
"""Rebuild the live site's picture-card grids in our pages.

  python tools/pull-card-grids.py            # every page listed in PAGES
  python tools/pull-card-grids.py <page.html>

The old site shows its services, games and artists as cards: a photo, a name,
sometimes a line or two of detail, and a button. The rebuild flattened each
card into a bare heading, because the photo is painted with a CSS
background-image and an <img> sweep never saw it. This puts the cards back.

It works off the live page: the card's photo, its name, its detail lines and
where its button goes. The matching run of headings in our page is replaced by
the grid, and any detail paragraph that the card now carries is removed with
it. Anything it does not recognise is left alone and the page is skipped, so a
page is either rebuilt whole or not touched.

A card the live site shows without a photo is left alone: two balloon packages
have no picture there either, so they stay as prose.
"""

import html
import io
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = "https://showmaqers.com/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; showmaqers-site-rebuild/1.0)"}
IMG_DIR = os.path.join(ROOT, "images", "live")

PAGES = [
    "hire-manpower-artists-for-events-party-in-delhi-gurugram-noida.html",
    "games-activities-on-rent-for-events-parties-delhi-ncr.html",
    "hire-best-male-female-dj-for-event-party-in-delhi-gurugram-noida-faridabad-manesar.html",
    "female-emcee-anchor-for-hire-for-events-parties-delhi-ncr.html",
    "diwali-rangoli-decorators-delhi-gurgaon-noida.html",
    "balloon-decorator-for-events-parties-delhi-ncr.html",
    "baby-shower-decorators-delhi-gurgaon-noida.html",
    "event-decorators-planners-delhi-gurgaon-noida.html",
]
NUMBERED = re.compile(r"^\s*\d+[.)]?\s+")


def norm(t):
    return re.sub(r"\s+", " ", t or "").strip().lower()


def live_html(page):
    r = requests.get(LIVE + page, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def cards_on(page_html):
    out = []
    for box in BeautifulSoup(page_html, "html.parser").select(".smue-service-box-obj"):
        holder = box.select_one(".smue-service-box-icon-holder div")
        m = re.search(r"url\(\s*'([^']+)'\s*\)", holder.get("style", "")) if holder else None
        head = box.select_one(".smue-service-box-heading-section")
        body = box.select_one(".smue-service-box-content-section")
        btn = box.select_one(".smue-service-box-button-section a")
        name = re.sub(r"\s+", " ", head.get_text(" ", strip=True)) if head else ""
        # the price sits in an h4 on the balloon cards and in a p on the rest
        lines = [re.sub(r"\s+", " ", el.get_text(" ", strip=True))
                 for el in (body.find_all(["p", "h3", "h4", "h5", "h6", "li"])
                            if body else [])]
        lines = [l for l in lines if l]
        if not name and lines:                     # the event page names the card here
            name, lines = lines[0], lines[1:]
        if m and name and btn and btn.get("href"):
            out.append({"img": m.group(1), "name": name, "lines": lines,
                        "href": btn["href"], "btn": btn.get_text(strip=True)})
    return out


def fetch_image(src):
    base = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(src.split("?")[0]))[:120]
    for p in ("images/" + base, "images/live/" + base):
        if os.path.exists(os.path.join(ROOT, p)):
            return p
    r = requests.get(LIVE + src.lstrip("/"), headers=UA, timeout=45)
    if not r.ok or not r.content:
        return None
    os.makedirs(IMG_DIR, exist_ok=True)
    io.open(os.path.join(IMG_DIR, base), "wb").write(r.content)
    return "images/live/" + base


def card_markup(c, src):
    name = html.escape(c["name"])
    detail = " · ".join(c["lines"])
    return (
        '          <div class="svc-card">\n'
        '            <img src="%s" alt="%s" loading="lazy" width="400" height="300">\n'
        '            <b>%s</b>\n'
        '%s'
        '            <a class="btn btn--hot" href="%s">%s</a>\n'
        '          </div>' % (
            src, name, name,
            ('            <small>%s</small>\n' % html.escape(detail)) if detail else '',
            html.escape(c["href"], quote=True), html.escape(c["btn"] or "Click here")))


LINE = re.compile(r"^\s*<(h[1-6]|p)>(.*)</\1>\s*$")


def rebuild(page):
    """Swap the run of bare headings for the grid, by line.

    Line surgery rather than a parse-and-write: re-serialising the document
    rewrites every attribute in the file and buries a 20-line change in a
    200-line diff.
    """
    cards = cards_on(live_html(page))
    if not cards:
        print("%-56s no cards on the live page" % page[:56]); return False

    path = os.path.join(ROOT, page)
    lines = io.open(path, encoding="utf-8").read().split("\n")
    text = {}                            # normalised line text -> indices, in order
    for i, line in enumerate(lines):
        m = LINE.match(line)
        if m:
            text.setdefault(norm(html.unescape(m.group(2))), []).append(i)

    at = []
    for c in cards:
        # a name can repeat -- two "Baby shower backdrop" packages at different
        # prices -- so each card takes the next line of that name, not the first
        where = text.get(norm(c["name"]), [])
        if not where:
            print("%-56s %r is not a line in our page, skipped"
                  % (page[:56], c["name"][:40])); return False
        at.append(where.pop(0))

    # The loose copies of what the card now says. A card may hold its detail in
    # one paragraph where our page split it into a price heading and a list, so
    # a line goes only if the card repeats it word for word.
    doomed = set(at)
    for c, i in zip(cards, at):
        carried = norm(" ".join(c["lines"]))
        j = i + 1
        while j < len(lines) and carried:
            m = LINE.match(lines[j])
            if not m:
                break
            said = norm(html.unescape(m.group(2)))
            if not said or said not in carried:
                break
            doomed.add(j); j += 1

    rows = []
    for c in cards:
        src = fetch_image(c["img"])
        if not src:
            print("%-56s could not fetch %s, skipped" % (page[:56], c["img"])); return False
        rows.append(card_markup(c, src))
    grid = '        <div class="svc-grid">\n%s\n        </div>' % "\n".join(rows)

    out = []
    for i, line in enumerate(lines):
        if i == min(at):
            out.append(grid)
        if i not in doomed:
            out.append(line)
    io.open(path, "w", encoding="utf-8", newline="").write("\n".join(out))
    print("%-56s %d cards, %d lines replaced" % (page[:56], len(cards), len(doomed)))
    return True


if __name__ == "__main__":
    todo = sys.argv[1:] or PAGES
    done = sum(bool(rebuild(p)) for p in todo)
    print("%d of %d pages rebuilt" % (done, len(todo)))
