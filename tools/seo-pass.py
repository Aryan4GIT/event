#!/usr/bin/env python
"""The search-engine pass over every page, as the pages stand now.

  python tools/seo-pass.py

Run it last: after build-seo-pages.py, pull-card-grids.py and any hand edits.
It is safe to run any number of times -- a second run changes nothing.

Why a pass, and not more of build-seo-pages.py
----------------------------------------------
The generated pages have been worked on since the build wrote them: card
grids, photo strips, extra pictures, copy fixed by hand. Re-running the build
would throw all of that away. So this reads each page as it is and touches
only what a search engine reads first:

  * the <title> and meta description, and the og:/twitter: copies of them
  * the JSON-LD block
  * width/height on <img>, and the hero picture's fetch priority
  * a "more like this" block between <!--related--> markers
  * the blog and games lists, between <!--pre--> markers, on the two hub
    pages that otherwise only fill them in with JavaScript

and it owns sitemap.xml, robots.txt, llms.txt and 404.html outright.

The video metadata comes from video-meta.json (tools/pull-video-meta.py).
"""

import glob
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import date

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.showmaqers.com"
TODAY = date.today().isoformat()
BRAND = " — SHOWMAQERS"
OG_DEFAULT = "images/og-showmaqers.jpg"     # 1200x630, the floral entrance arch

# the business, once. index.html carries the full LocalBusiness; every other
# page names it as the provider with the same @id, so the two are one entity.
BUSINESS = {
    "@type": "LocalBusiness",
    "@id": SITE + "/#business",
    "name": "SHOWMAQERS",
    "url": SITE + "/",
    "telephone": "+919811788643",
    "image": SITE + "/" + OG_DEFAULT,
    "address": {"@type": "PostalAddress",
                "streetAddress": "160, Dhappa Colony, Raipur Khurd, Chattarpur",
                "addressLocality": "New Delhi", "postalCode": "110068",
                "addressRegion": "Delhi", "addressCountry": "IN"},
}
PUBLISHER = {"@type": "Organization", "@id": SITE + "/#business", "name": "SHOWMAQERS",
             "url": SITE + "/",
             "logo": {"@type": "ImageObject", "url": SITE + "/images/logo-icon.png"}}
WEBSITE = {"@type": "WebSite", "url": SITE + "/", "name": "SHOWMAQERS"}

# written by hand: their titles, descriptions and JSON-LD are left as they are
HUBS = ["index.html", "manpower.html", "games.html", "blog.html", "vendors.html"]
SKIP = {"admin.html", "404.html"}

# the old WordPress archive pages: a list of post titles with no links and
# nothing of their own. They keep their URLs, out of the index.
NOINDEX = {"blog/default-post.html", "blog/category/events.html",
           "blog/category/games-activities.html", "blog/category/manpower-artists.html",
           "blog/category/uncategorized.html"}

# events we ran, not services anyone can book -- a page about one, not a Service
CASE_STUDIES = {"decoration-maruti-showroom.html", "decorator-lohri-ambience-mall-gurgaon.html",
                "gigabyte-corporate-event.html", "jln-stadium-food-festival.html",
                "ring-ceremony-ashoka-hotel.html", "startup-buddy-grand-hotel.html",
                "wedding-ceremony-palm-town-country-club.html", "yamaha-bike-promotion-event.html"}
PAGE_TYPE = {"contact.html": "ContactPage", "gallery.html": "CollectionPage",
             "services.html": "CollectionPage", "sitemap.html": "CollectionPage"}

# where the old description was a stub ("Contact us...", "1. Ring Ceremony
# at The Ashoka Hotel...") and the page has no prose to take one from
DESCRIPTIONS = {
    "contact.html": "Call SHOWMAQERS on +91 98117 88643 or +91 99107 72449, or write to "
                    "info@showmaqers.com. Office at Chattarpur, New Delhi 110068.",
    "gallery.html": "Ring ceremonies, weddings, corporate events, a food festival and mall and "
                    "showroom décor: events SHOWMAQERS has planned and decorated across Delhi NCR.",
    "services.html": "Wedding and flower decoration, corporate events, stage fabrication, theme "
                     "parties, celebrity management and photo and video shoots across Delhi NCR.",
}

PHONE_PREFIX = re.compile(r"^\s*\+?\s*91[-\s]?\d[\d\s-]{6,}\s*[-–—|:]?\s*")
BRAND_TAIL = re.compile(r"(\s*[-–—|:]\s*show\s*maqers)+\s*$", re.I)
# the old copy opens most paragraphs with the page's name: "Ball Pool On Rent :- ..."
LEAD_IN = re.compile(r"^[^.:]{3,50}\s*:-+\s*")
ACRONYMS = {"NCR", "AC", "DJ", "DJS", "LED", "VR", "3D", "F&B", "BBQ", "MC", "JLN", "SHOWMAQERS"}
SMALL = {"a", "an", "and", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with", "&"}
PLACES = {"delhi", "gurugram", "gurgaon", "noida", "faridabad", "ghaziabad", "manesar", "india",
          "showmaqers"}


def load_build():
    """build-seo-pages.py, for its page sections and its page shell."""
    spec = importlib.util.spec_from_file_location(
        "build", os.path.join(ROOT, "tools", "build-seo-pages.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def squeeze(s):
    return " ".join((s or "").split())


def text_of(fragment):
    return squeeze(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def shouting(s):
    letters = [c for c in s if c.isalpha()]
    return len(letters) > 8 and sum(c.isupper() for c in letters) / len(letters) > .8


def title_case(s):
    """The old site wrote most titles in capitals. A result in capitals reads
    as shouting and is the first thing Google rewrites, so put it in title
    case, keeping the acronyms."""
    if not shouting(s):
        return s
    out = []
    for n, word in enumerate(re.sub(r"\s*\|\s*", " | ", s).split()):
        if word.upper() in ACRONYMS:
            out.append(word.upper())
        elif n and word.lower() in SMALL:
            out.append(word.lower())
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in word.split("-")))
    return " ".join(out)


def sentence_case(s):
    if not shouting(s):
        return s
    words = s.lower().split()
    out = [w.upper() if w.upper() in ACRONYMS else w.capitalize() if w in PLACES else w
           for w in words]
    return (" ".join(out))[:1].upper() + " ".join(out)[1:]


def fit(s, limit=158):
    """Search results show about 155-160 characters of a description. Cut at
    the last full sentence that fits, or at a word with an ellipsis."""
    s = squeeze(s)
    if len(s) <= limit:
        return s
    cut = s[:limit + 1]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if stop >= 90:
        return cut[:stop + 1]
    return cut[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:–—-") + "…"


def clean_title(raw, h1):
    t = squeeze(PHONE_PREFIX.sub("", html.unescape(raw)))
    t = title_case(BRAND_TAIL.sub("", t).strip())
    # "Gigabyte", "Maruti Showroom": the old theme's short titles say less
    # than the heading on the same page does
    if len(t) < 30 and len(t) < len(h1) <= 60:
        t = h1
    if "showmaqer" not in t.lower() and len(t) + len(BRAND) <= 62:
        t += BRAND
    return t


def body_copy(page):
    """The page's own prose, for a description when the old one was a stub."""
    article = page[page.find("<article"):page.find('<div class="tail">')]
    out = []
    for p in re.findall(r"<p>(.*?)</p>", article, re.S):
        p = text_of(p)
        # skip contact lines and price-list labels ("Ribbons: Happy birthday foil...")
        if len(p) < 40 or "@" in p or re.match(r"[\w ]{2,20}:\s", p):
            continue
        p = LEAD_IN.sub("", p)
        out.append(sentence_case(p).rstrip(" .:") + ".")
        if len(" ".join(out)) > 140:
            break
    return " ".join(out)


def tidy(s):
    """The old copy runs sentences together with dot leaders -- "in Delhi –
    NCR …..at very reasonable price ……Children love it". Make them stops."""
    s = squeeze(s)
    if re.search(r"\S\s?\.{3,}$", s):         # cut off mid-word by the old theme
        s = (s.rstrip(".").rsplit(" ", 1)[0] if len(s) >= 150 else s.rstrip(".")).rstrip(" ,") + "…"
    s = re.sub(r"\s*(?:[.…]{2,}|…)\s*(?=\S)", ". ", s)
    s = re.sub(r"\s+([.,])", r"\1", s)
    s = re.sub(r"([.,])\1+", r"\1", s)
    return re.sub(r"\. ([a-z])", lambda m: ". " + m.group(1).upper(), s)


def key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


SEEN_DESC = set()


def clean_desc(raw, page, path, name, title):
    if path in DESCRIPTIONS:
        d = DESCRIPTIONS[path]
    else:
        d = squeeze(PHONE_PREFIX.sub("", html.unescape(raw)))
        # a description that only repeats the title tells the reader nothing new
        k = key(BRAND_TAIL.sub("", d))
        same = len(d) < 110 and any(x and (k.startswith(x) or x.startswith(k))
                                    for x in (key(name), key(BRAND_TAIL.sub("", title))))
        if len(d) < 70 or d.endswith("...") and len(d) < 100 or same:
            if path in CASE_STUDIES:
                d = ("%s: an event SHOWMAQERS planned and decorated, in photographs. Wedding, "
                     "corporate and party planners across Delhi NCR." % name)
            else:
                d = body_copy(page) or (
                    "%s. Planned, set up and run by SHOWMAQERS across Delhi, Gurugram, Noida, "
                    "Faridabad, Ghaziabad and Manesar." % name)
        d = fit(tidy(sentence_case(d)))
    if d in SEEN_DESC:
        d = fit("%s. %s" % (name, d))
    SEEN_DESC.add(d)
    return d


def set_meta(page, attr, key, value):
    tag = '<meta %s="%s" content="%s">' % (attr, key, html.escape(value, quote=True))
    pat = re.compile(r'<meta %s="%s" content="[^"]*">' % (attr, re.escape(key)))
    return pat.sub(lambda m: tag, page, count=1) if pat.search(page) else page


# ── images ──────────────────────────────────────────────────────────────────

SIZES = {}


def size_of(src, path):
    """(width, height) of a local picture, or None."""
    if src.startswith(("http", "data:", "${")) or "${" in src:
        return None
    src = src.split("?")[0]
    full = os.path.normpath(os.path.join(ROOT, src.lstrip("/")) if src.startswith("/")
                            else os.path.join(ROOT, os.path.dirname(path), src))
    if full not in SIZES:
        try:
            SIZES[full] = Image.open(full).size
        except Exception:
            SIZES[full] = None
    return SIZES[full]


def size_images(page, path):
    """Give every picture its width and height, so the browser can hold its
    place before it arrives and the text does not jump as pictures load. CSS
    still sets the size; the attributes only give it the shape."""
    def one(m):
        tag = m.group(0)
        if " width=" in tag:
            return tag
        src = re.search(r'\ssrc="([^"]+)"', tag)
        wh = src and size_of(html.unescape(src.group(1)), path)
        if not wh:
            return tag
        return tag[:4] + ' width="%d" height="%d"' % wh + tag[4:]
    parts = re.split(r"(<script\b.*?</script>)", page, flags=re.S)
    return "".join(p if p.startswith("<script") else re.sub(r"<img\b[^>]*>", one, p)
                   for p in parts)


def drop_junk_hero(page, path):
    """Two pages took a spinner or a 98px avatar from the old theme as their
    lead picture."""
    def one(m):
        src = re.search(r'src="([^"]+)"', m.group(0)).group(1)
        wh = size_of(html.unescape(src), path)
        return "" if src.endswith(".gif") or (wh and min(wh) < 120) else m.group(0)
    return re.sub(r'\n\s*<img class="hero-shot"[^>]*>', one, page)


def hero_first(page):
    """The lead picture is what the page is waiting on: ask for it first."""
    return re.sub(r'<img class="hero-shot"(?![^>]*fetchpriority)',
                  '<img class="hero-shot" fetchpriority="high"', page, count=1)


def finish(page, path):
    """What every page gets, hand-written or not."""
    # a share card needs a wide photograph, not the square logo
    for key in ("og:image", "twitter:image"):
        attr = "property" if key.startswith("og") else "name"
        page = page.replace('<meta %s="%s" content="%s/images/logo-mark.webp">' % (attr, key, SITE),
                            '<meta %s="%s" content="%s/%s">' % (attr, key, SITE, OG_DEFAULT))
    return hero_first(size_images(page, path))


# ── structured data ─────────────────────────────────────────────────────────

def videos_on(page, meta, fallback):
    out, seen = [], set()
    for vid in re.findall(r'<iframe[^>]+src="[^"]*youtube(?:-nocookie)?\.com/embed/([\w-]{11})', page):
        if vid in seen or vid not in meta:
            continue
        seen.add(vid)
        v = meta[vid]
        node = {"@type": "VideoObject", "name": title_case(v["title"] or fallback),
                "description": fit(v["description"] or fallback, 300),
                "thumbnailUrl": ["https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid],
                "uploadDate": v["uploadDate"],
                "embedUrl": "https://www.youtube.com/embed/" + vid}
        if v.get("duration"):
            node["duration"] = v["duration"]
        out.append(node)
    return out


def rebuild_jsonld(page, path, name, desc, og_image, meta):
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', page, re.S)
    if not m:
        return page
    data = json.loads(m.group(2))
    url = "%s/%s" % (SITE, path)
    kind = PAGE_TYPE.get(path) or ("WebPage" if path in CASE_STUDIES else None)
    graph = []
    for node in data.get("@graph", [data]):
        t = node.get("@type")
        if t == "BreadcrumbList":
            for item in node["itemListElement"]:
                item["name"] = title_case(item["name"])
                if item["item"].endswith("/index.html"):
                    item["item"] = SITE + "/"
            graph.append(node)
        elif t == "Service" and not kind:
            node.update(name=name, serviceType=name, description=desc, provider=BUSINESS)
            if og_image != OG_DEFAULT:
                node["image"] = "%s/%s" % (SITE, og_image)
            graph.append(node)
        elif t == "BlogPosting":
            node.update(description=desc, url=url, author=PUBLISHER, publisher=PUBLISHER)
            graph.append(node)
        elif t in ("Service", "VideoObject", "ContactPage", "CollectionPage", "WebPage"):
            continue                      # rebuilt below
        else:
            graph.append(node)            # FAQPage and anything else: as written
    if kind:
        node = {"@type": kind, "url": url, "name": name, "description": desc, "isPartOf": WEBSITE}
        if kind == "ContactPage":
            node["mainEntity"] = BUSINESS
        graph.append(node)
    graph += videos_on(page, meta, name)
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph},
                    ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return page[:m.start(2)] + ld + page[m.end(2):]


# ── links ───────────────────────────────────────────────────────────────────

RELATED_HEADS = {"Blog": "More from the blog",
                 "Games &amp; activities on rent": "More games &amp; activities on rent",
                 "Artists &amp; manpower": "More artists &amp; manpower",
                 "Décor &amp; planning": "More décor &amp; planning",
                 "Events we have run": "More events we have run",
                 "Shows": "More shows &amp; activities"}


def section_of(path, build):
    if path in CASE_STUDIES:
        return "Events we have run"
    for name, match in build.SECTIONS:
        if match(path):
            # the build's catch-all also holds the handful of shows
            return "Shows" if name == "Events we have run" else name
    return None


def related_block(path, groups, names):
    """Six pages from the same section, the three either side of this one in
    title order. Each page gets six links out and six in, so none is
    reachable only through the directory, and the set is stable from run to
    run instead of reshuffling on every build."""
    group = groups.get(path)
    peers = sorted((p for p, g in groups.items() if g == group), key=lambda p: names[p].lower())
    if len(peers) < 2:
        return ""
    i, n = peers.index(path), min(6, len(peers) - 1)
    picks = [peers[(i + k) % len(peers)] for k in range(-(n // 2), n - n // 2 + 1) if k]
    prefix = "../" * path.count("/")
    items = "\n".join('            <li><a href="%s%s">%s</a></li>' % (prefix, p, html.escape(names[p]))
                      for p in picks[:n])
    return ("<!--related-->\n        <nav class=\"related\" aria-labelledby=\"related-h\">\n"
            "          <h2 id=\"related-h\">%s</h2>\n          <ul>\n%s\n          </ul>\n"
            "        </nav>\n        <!--/related-->\n        " % (RELATED_HEADS[group], items))


def put_related(page, block):
    page = re.sub(r"<!--related-->.*?<!--/related-->\s*", "", page, flags=re.S)
    return page.replace('<div class="tail">', block + '<div class="tail">', 1) if block else page


def load_js_data(name, var):
    src = open(os.path.join(ROOT, name), encoding="utf-8").read()
    start = src.index("window.%s" % var)
    body = src[src.index("=", start) + 1:].strip().rstrip(";")
    return json.loads(body)


def prerender(page, opener, inner):
    """Fill a container the page's script fills, with the same markup the
    script writes. A crawler that runs no JavaScript -- and every AI crawler
    is one -- saw an empty list and no links to the pages it lists."""
    pat = re.compile(r"(%s)(?:<!--pre-->.*?<!--/pre-->)?(</div>)" % re.escape(opener), re.S)
    return pat.sub(lambda m: m.group(1) + "<!--pre-->" + inner + "<!--/pre-->" + m.group(2), page, count=1)


def hub_blog(page):
    e = lambda s: html.escape(str(s or ""), quote=True)
    cards = "".join("""
    <a class="post-card" href="blog/%s.html">
      %s
      <div class="pc-body">
        %s
        <h2>%s</h2>
        <p>%s</p>
        <span class="more">Read &rarr;</span>
      </div>
    </a>""" % (e(p["s"]), '<img src="%s" alt="" loading="lazy">' % e(p["i"][0]) if p.get("i") else "",
               '<time datetime="%s">%s</time>' % (e(p["d"]), e(p["w"])) if p.get("w") else "",
               e(p["t"]), e(p["x"])) for p in load_js_data("blog-data.js", "POSTS"))
    return prerender(page, '<div class="posts" id="postList">', cards)


def hub_games(page):
    e = lambda s: html.escape(str(s or ""), quote=True)
    for key, group in load_js_data("games-data.js", "GAMES").items():
        cards = []
        for it in group.get("items") or []:
            shots = it.get("i") or []
            href = re.sub(r"^https?://[^/]+/", "", it.get("u") or "")
            fig = ('<figure data-imgs="%s" data-cap="%s">\n          <img src="%s" alt="%s" loading="lazy">\n          %s\n        </figure>'
                   % (e("|".join(shots)), e(it["n"]), e(shots[0]), e(it["n"]),
                      '<span class="more">+%d</span>' % (len(shots) - 1) if len(shots) > 1 else "")
                   if shots else
                   '<figure class="noimg" aria-hidden="true">\n          <b>%s</b><small>Photo on request</small>\n        </figure>' % e(it["n"][:1]))
            spec = ('<ul class="spec">%s</ul>' % "".join("<li>%s</li>" % e(d) for d in it["d"])) if it.get("d") else ""
            cards.append('<article class="game">\n        %s\n        %s\n          <h3>%s</h3>\n          <p>%s</p>\n          %s\n        %s\n      </article>'
                         % (fig, '<a class="game-body" href="%s">' % e(href) if href else '<div class="game-body">',
                            e(it["n"]), e(it["b"]), spec, "</a>" if href else "</div>"))
        page = prerender(page, '<div class="games" data-games="%s">' % key, "".join(cards))
    return page


# ── the files this pass owns ────────────────────────────────────────────────

def git_dates():
    """The date each file last changed in git, and the files changed since."""
    out = subprocess.run(["git", "log", "--format=@%cs", "--name-only"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout
    dates, day = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            day = line[1:]
        elif line and line not in dates:
            dates[line] = day
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8").stdout
    changed = {l[3:].strip().strip('"') for l in dirty.splitlines()}
    return dates, changed


def write_sitemap(paths):
    """lastmod is the day the page last changed, not the day this ran. A
    sitemap that marks every page as changed on every build teaches Google
    to ignore its dates altogether."""
    dates, changed = git_dates()
    order = HUBS + sorted(p for p in paths if p not in HUBS)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in order:
        day = TODAY if p in changed or p not in dates else dates[p]
        loc = SITE + "/" + ("" if p == "index.html" else p)
        lines.append("  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (html.escape(loc), day))
    lines.append("</urlset>")
    save("sitemap.xml", "\n".join(lines) + "\n")
    return len(order)


def write_llms(groups, names, descs):
    """llms.txt: a plain map of the site for language-model tools. Google
    ignores it; it costs nothing and some assistants read it."""
    out = ["# SHOWMAQERS", "",
           "> Wedding, destination and corporate event planners and decorators in Delhi NCR "
           "(Delhi, Gurugram, Noida, Faridabad, Ghaziabad, Manesar), working pan India. Décor, "
           "stage fabrication, artists and manpower, and games and activities on rent.", "",
           "- Phone: +91 98117 88643, +91 99107 72449 (artist bookings)",
           "- Email: info@showmaqers.com",
           "- Office: 160, Dhappa Colony, Raipur Khurd, Chattarpur, New Delhi 110068", "",
           "## Main pages", "",
           "- [Home](%s/): who we are, services, gallery, contact" % SITE,
           "- [Artists & manpower](%s/manpower.html): anchors, DJs, dancers, singers and crew for hire" % SITE,
           "- [Games & activities on rent](%s/games.html): rides, arcade, carnival stalls and shows" % SITE,
           "- [Blog](%s/blog.html)" % SITE,
           "- [Every page](%s/sitemap.html)" % SITE]
    for head in ("Décor &amp; planning", "Artists &amp; manpower", "Shows",
                 "Games &amp; activities on rent", "Events we have run", "Blog"):
        pages = sorted((p for p, g in groups.items() if g == head), key=lambda p: names[p].lower())
        if not pages:
            continue
        out += ["", "## " + html.unescape(RELATED_HEADS[head][5:]).capitalize(), ""]
        out += ["- [%s](%s/%s): %s" % (names[p], SITE, p, descs[p]) for p in pages]
    save("llms.txt", "\n".join(out) + "\n")


def write_404(build):
    """Served for any missing path, at any depth, so every link in it is
    root-relative. Never indexed."""
    rel = build.rel
    build.rel = lambda path: "/"
    try:
        page = build.shell("404.html", "Page not found" + BRAND,
                           "This page has moved or no longer exists.",
                           [("Home", "index.html"), ("Page not found", None)],
                           "        <h1>That page is not here.</h1>\n"
                           "        <p>It may have moved when the site was rebuilt. Everything we do "
                           "is listed on one page, or call us on +91 98117 88643.</p>\n"
                           '        <p><a href="/sitemap.html">See every page</a> &middot; '
                           '<a href="/">Go to the home page</a></p>',
                           {"@context": "https://schema.org", "@type": "WebPage", "name": "Page not found"})
    finally:
        build.rel = rel
    page = re.sub(r'<link rel="canonical"[^>]*>\n|<meta property="og:url"[^>]*>\n', "", page)
    page = page.replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"', 1)
    save("404.html", finish(page, "404.html"))


def save(path, text):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    build = load_build()
    meta_path = os.path.join(ROOT, "video-meta.json")
    videos = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}

    paths = sorted(os.path.relpath(p, ROOT).replace("\\", "/") for p in
                   glob.glob(os.path.join(ROOT, "*.html")) + glob.glob(os.path.join(ROOT, "blog", "*.html"))
                   + glob.glob(os.path.join(ROOT, "blog", "category", "*.html")))
    paths = [p for p in paths if p not in SKIP]
    pages = {p: open(os.path.join(ROOT, p), encoding="utf-8").read() for p in paths}

    # first the names, because every page's related links need all of them
    names, groups, descs = {}, {}, {}
    for p, page in pages.items():
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        names[p] = title_case(text_of(h1.group(1))) if h1 else p
        if p not in HUBS and p not in NOINDEX and p not in PAGE_TYPE:
            groups[p] = section_of(p, build)

    for p in paths:
        page = pages[p]
        if p in NOINDEX:
            # out of the index: only the robots tag and the share image matter
            if 'name="robots"' not in page:
                page = page.replace('<meta name="description"', '<meta name="robots" content="noindex, follow">\n<meta name="description"', 1)
            page = drop_junk_hero(page, p)
        elif p not in HUBS:
            title = clean_title(re.search(r"<title>(.*?)</title>", page, re.S).group(1), names[p])
            raw = re.search(r'<meta name="description" content="([^"]*)"', page)
            desc = clean_desc(raw.group(1) if raw else "", page, p, names[p], title)
            page = re.sub(r"<title>.*?</title>", lambda m: "<title>%s</title>" % html.escape(title, quote=False),
                          page, count=1, flags=re.S)
            for attr, key, value in (("name", "description", desc), ("property", "og:title", title),
                                     ("property", "og:description", desc), ("name", "twitter:title", title),
                                     ("name", "twitter:description", desc)):
                page = set_meta(page, attr, key, value)
            page = drop_junk_hero(page, p)
            og = re.search(r'<meta property="og:image" content="%s/([^"]+)"' % re.escape(SITE), page)
            og_image = og.group(1) if og else OG_DEFAULT
            page = rebuild_jsonld(page, p, BRAND_TAIL.sub("", names[p]), desc, og_image, videos)
            if p in groups:
                page = put_related(page, related_block(p, groups, names))
            descs[p] = desc
        if p == "blog.html":
            page = hub_blog(page)
        elif p == "games.html":
            page = hub_games(page)

        page = finish(page, p)
        if page != pages[p]:
            save(p, page)
            pages[p] = page

    write_404(build)
    n = write_sitemap([p for p in paths if p not in NOINDEX])
    save("robots.txt", "User-agent: *\nAllow: /\nDisallow: /admin.html\n\nSitemap: %s/sitemap.xml\n" % SITE)
    write_llms(groups, names, descs)
    print("%d pages checked, sitemap.xml with %d urls, robots.txt, llms.txt, 404.html" % (len(paths), n))


if __name__ == "__main__":
    sys.exit(main())
