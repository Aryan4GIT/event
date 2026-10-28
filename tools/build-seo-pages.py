#!/usr/bin/env python
"""Build a real HTML page for every URL the old showmaqers.com had.

Run from the repo root:  python tools/build-seo-pages.py

Why this exists
---------------
The hand-written pages are hubs: one URL carries 20 blog posts, another 48
games, another 22 artist roles. A search engine can only rank a URL for one
thing, so all of that content was competing for a single listing and most of
it could not be found at all. showmaqers-content.json is a scrape of the old
WordPress site -- 148 URLs, their titles, descriptions, copy, images and
videos -- and this script turns each of those back into a page.

Each page is written at the SAME PATH the old site used. That is the whole
point: those URLs are the ones with ranking history and inbound links, so
when this site replaces the WordPress one they keep working with no
redirects to configure and nothing to lose in the handover.

Nothing here is rendered by JavaScript. A crawler that runs no scripts still
sees the title, the copy, the images and the structured data.
"""

import html
import json
import os
import re
import sys
from datetime import date
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.showmaqers.com"          # one place to change the origin
PHONE = "+919811788643"
TODAY = date.today().isoformat()

# The old site put its phone numbers in <h?> tags in the header, so they come
# through the scrape as headings. They are not headings.
JUNK_HEADING = re.compile(r"^\s*(call\s*:|\+?91[\d\s\-]{8,})", re.I)

# index.html and / are the one place the rebuild is better than the scrape,
# so they keep the hand-written page.
SKIP = {"", "index.html"}


# the separator is optional: five pages run the number straight into the
# title with nothing but a space -- "+91-9910772449 HIRE JUGGLER FOR..."
PHONE_PREFIX = re.compile(r"^\s*\+?\s*91[-\s]?\d[\d\s-]{6,}\s*[-–—|:]?\s*")


def clean_title(title):
    """The live <title> on most pages starts with the sales number, e.g.
    "+91-9910772449 - BALLOON DECORATORS FOR EVENTS & PARTIES...". That is
    the first thing a searcher reads in the result, and it pushes the words
    they searched for past the truncation point. Strip it, squeeze the
    double spaces the old theme left behind, and put the brand on the end
    where it belongs when it is not already somewhere in the title.
    """
    title = PHONE_PREFIX.sub("", title or "").strip()
    title = " ".join(title.split())
    if not title:
        return "SHOWMAQERS"
    if "showmaqer" not in title.lower() and len(title) <= 55:
        title += " — SHOWMAQERS"
    return title


def esc(s):
    return html.escape(str(s or ""), quote=True)


SEEN_DESC = set()


def unique_desc(desc, name):
    """Two pages must not share a meta description.

    The old site had a few pairs that did -- the two card-party posts, the
    two balloon packages -- and a couple that were truncated mid-sentence on
    the way in. Leading with the page's own name fixes both, and only for
    the pages that need it, so the hand-written copy stays as written.
    """
    desc = (desc or "").strip()
    if desc and desc not in SEEN_DESC:
        SEEN_DESC.add(desc)
        return desc
    joined = ("%s. %s" % (name.rstrip(" ."), desc)).strip()
    if len(joined) > 158:
        joined = joined[:155].rsplit(" ", 1)[0] + "..."
    SEEN_DESC.add(joined)
    return joined


def rel(path):
    """How many ../ a page at `path` needs to reach the repo root."""
    return "../" * path.count("/")


def load_posts():
    """blog-data.js is `window.POSTS = [ ...json... ];` -- read it as JSON.

    The blog posts come from here rather than from the scrape because this
    file already marks up headings and list items, which the flat scrape
    body does not.
    """
    src = open(os.path.join(ROOT, "blog-data.js"), encoding="utf-8").read()
    return json.loads(src[src.index("["):src.rindex("]") + 1])


def load_pages():
    """The live crawl: tools/crawl-live-site.py writes it.

    Each page arrives already deduplicated to one spelling, with the site
    chrome removed, and with its copy as [kind, text, tag] triples in
    document order instead of a flat list of strings -- so a heading can be
    laid out as a heading and a bullet as a bullet.
    """
    with open(os.path.join(ROOT, "showmaqers-site.json"), encoding="utf-8") as f:
        return json.load(f)["pages"]


def local_image(src):
    """Where this picture lives in the repo, or None.

    Images already carried over by hand sit in images/; everything the
    crawler pulled down is in images/live/. Prefer the hand-picked copy when
    both exist, so the pages keep using the files the rest of the site does.
    """
    name = os.path.basename(urlparse(src).path)
    if not name:
        return None
    for path in ("images/" + name, "images/live/" + name):
        if os.path.exists(os.path.join(ROOT, path)):
            return path
    return None


def keep_images(images):
    """Only pictures that are actually in the repo, each one once.

    `images` is either the crawl's [{src, alt}] or a plain list of paths.
    """
    out, seen = [], set()
    for img in images:
        src = img["src"] if isinstance(img, dict) else img
        alt = (img.get("alt") or "") if isinstance(img, dict) else ""
        path = local_image(src) if src.startswith("http") else (
            src if os.path.exists(os.path.join(ROOT, src)) else None)
        if path and path not in seen:
            seen.add(path)
            out.append({"path": path, "alt": alt})
    return out


def split_faq(body):
    """Return (copy before the FAQ, [(question, answer), ...]).

    The old pages end with alternating question/answer blocks under a
    'Frequently Asked Questions' heading. Questions end in '?'.
    """
    mark = next((i for i, b in enumerate(body)
                 if b[1].strip().lower().startswith("frequently asked question")), None)
    if mark is None:
        return body, []
    rest, pairs = body[mark + 1:], []
    i = 0
    while i < len(rest) - 1:
        if rest[i][1].rstrip().endswith("?"):
            pairs.append((rest[i][1].strip(), rest[i + 1][1].strip()))
            i += 2
        else:
            i += 1
    return body[:mark], pairs


def nav(prefix, here=""):
    link = lambda href, label: '<a href="%s%s"%s>%s</a>' % (
        prefix, href, ' aria-current="page"' if href == here else "", label)
    return """<header class="nav" id="nav">
  <div class="wrap">
    <div class="nav-in">
      <a class="brand" href="{p}index.html">
        <img src="{p}images/logo-mark.webp" alt="SHOWMAQERS logo">
        <span><b>SHOWMAQERS</b><small>Wedding &amp; Event Planner</small></span>
      </a>
      <nav class="nav-links" id="menu" aria-label="Main">
        {links}
      </nav>
      <a class="btn btn--hot" href="tel:+919910772449">Call<span class="num">&nbsp;99107 72449</span></a>
      <button class="burger" id="burger" aria-expanded="false" aria-controls="menu" aria-label="Menu"><i></i><i></i><i></i></button>
    </div>
  </div>
</header>""".format(p=prefix, links="\n        ".join([
        link("index.html#services", "Services"),
        link("manpower.html", "Artists"),
        link("games.html", "Games"),
        link("blog.html", "Blog"),
        link("index.html#gallery", "Gallery"),
        link("index.html#about", "About"),
        link("vendors.html", "Join us"),
        link("index.html#contact", "Contact"),
    ]))


def footer(prefix):
    return """<footer>
  <div class="wrap foot">
    <a class="brand" href="{p}index.html">
      <img src="{p}images/logo-mark.webp" alt="">
      <span><b>SHOWMAQERS</b><small>Wedding &amp; Event Planner</small></span>
    </a>
    <nav aria-label="Footer">
      <a href="{p}index.html#services">Services</a><a href="{p}manpower.html">Artists</a><a href="{p}games.html">Games</a><a href="{p}blog.html">Blog</a><a href="{p}vendors.html">Join us</a>
      <a href="{p}index.html#gallery">Gallery</a><a href="{p}index.html#about">About</a><a href="{p}index.html#contact">Contact</a><a href="{p}sitemap.html">All pages</a>
    </nav>
    <p>SHOWMAQERS &middot; All rights reserved</p>
  </div>
</footer>""".format(p=prefix)


# The shell scripts: just the nav, the menu and the scroll bar. The generated
# pages render nothing, so they do not need any of the hub pages' renderers.
SHELL_JS = """<script>
(() => {
  const root = document.documentElement;
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) root.classList.add('anim');
  const nav = document.getElementById('nav'), menu = document.getElementById('menu'),
        burger = document.getElementById('burger'), bar = document.getElementById('progress');
  const onScroll = () => {
    nav.classList.toggle('is-stuck', scrollY > 30);
    const max = root.scrollHeight - innerHeight;
    bar.style.width = (max > 0 ? (scrollY / max) * 100 : 0) + '%';
  };
  addEventListener('scroll', onScroll, { passive: true }); onScroll();
  const setMenu = (open) => { burger.setAttribute('aria-expanded', open); menu.classList.toggle('open', open); };
  burger.addEventListener('click', () => setMenu(burger.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('click', e => { if (e.target.tagName === 'A') setMenu(false); });
  addEventListener('resize', () => setMenu(false));
  const io = new IntersectionObserver((es) => {
    for (const e of es) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }, { rootMargin: '-5% 0px -5% 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
})();
</script>"""


def shell(path, title, description, crumbs, article, jsonld, og_image=None):
    """Wrap one page's article in the site shell and its <head>."""
    p = rel(path)
    canonical = "%s/%s" % (SITE, path)
    img = "%s/%s" % (SITE, og_image) if og_image else "%s/images/logo-mark.webp" % SITE
    crumb = " &middot; ".join(
        ('<a href="%s%s">%s</a>' % (p, href, esc(label))) if href else esc(label)
        for label, href in crumbs)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{ogtype}">
<meta property="og:site_name" content="SHOWMAQERS">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{img}">
<link rel="icon" href="{p}images/logo-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400..800;1,6..96,400..700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{p}site.css">
<link rel="stylesheet" href="{p}content.css">
<script type="application/ld+json">{jsonld}</script>
</head>
<body>

<div class="aurora" aria-hidden="true"><i></i><i></i><i></i></div>
<div class="grain" aria-hidden="true"></div>
<div class="progress" id="progress" aria-hidden="true"></div>

{nav}

<main>
  <section class="band">
    <div class="wrap">
      <article class="article">
        <p class="crumb">{crumb}</p>
{article}
        <div class="tail">
          <a class="back" href="{p}sitemap.html" style="margin:0">&larr; Everything we do</a>
          <a class="btn btn--hot" href="{p}index.html#contact">Plan my event</a>
        </div>
      </article>
    </div>
  </section>
</main>

{footer}
{js}
</body>
</html>
""".format(title=esc(title), desc=esc(description), canonical=esc(canonical), img=esc(img),
           ogtype="article" if path.startswith("blog/") else "website",
           p=p, jsonld=json.dumps(jsonld, ensure_ascii=False, separators=(",", ":")),
           nav=nav(p), footer=footer(p), js=SHELL_JS, crumb=crumb, article=article)


def breadcrumbs(crumbs, path):
    items = []
    for n, (label, href) in enumerate(crumbs, 1):
        item = {"@type": "ListItem", "position": n, "name": label}
        if href is not None:
            item["item"] = "%s/%s" % (SITE, href)
        else:
            item["item"] = "%s/%s" % (SITE, path)
        items.append(item)
    return {"@type": "BreadcrumbList", "itemListElement": items}


def build_scraped(entry, posts_by_slug):
    """One page from one crawled page."""
    path = urlparse(entry["url"]).path.lstrip("/")
    if path in SKIP or path.replace(".html", "") in SKIP:
        return None
    if path.startswith("blog/") and path[5:-5] in posts_by_slug:
        return None                      # the blog data builds these, better

    title = clean_title(entry["title"])
    desc = (entry["description"] or "").strip()
    body, faq = split_faq(entry["body"])
    images = keep_images(entry["images"])
    videos = [v for v in entry.get("youtube") or [] if "/embed/" in v or "watch?v=" in v]

    h1 = body[0][1].strip() if body and body[0][0] == "h" else title
    if body and body[0][0] == "h" and body[0][1].strip() == h1:
        body = body[1:]
    if not desc:
        desc = (body[0][1][:155] + "...") if body else title
    desc = unique_desc(desc, h1)

    # Fold the source's heading levels onto h2/h3 relative to the shallowest
    # one the page actually uses, not to the absolute tag. The balloon price
    # list is written entirely in <h4>/<h5>, so keying off the tag name alone
    # gave it 58 h3s under an h1 and no h2 at all.
    used = sorted({tag for kind, txt, tag in body if kind == "h"})
    top = used[0] if used else "h2"

    out = ['        <h1>%s</h1>' % esc(h1)]
    if images:
        out.append('        <img class="hero-shot" src="%s%s" alt="%s" width="1200" height="675">'
                   % (rel(path), esc(images[0]["path"]), esc(images[0]["alt"] or h1)))

    open_list = False
    for kind, txt, tag in body:
        txt = txt.strip()
        if not txt:
            continue
        if kind == "li" and not open_list:
            out.append("        <ul>"); open_list = True
        elif kind != "li" and open_list:
            out.append("        </ul>"); open_list = False
        if kind == "h":
            # keep the level the source used, folded into h2/h3. The balloon
            # page is a price list where each package name is an <h4> and its
            # price another; flattening every heading to <h2> would make the
            # package and its price siblings and leave the page with 59 of
            # them and no outline at all.
            out.append("        <%(t)s>%(x)s</%(t)s>"
                       % {"t": "h2" if tag == top else "h3", "x": esc(txt)})
        elif kind == "li":
            out.append("          <li>%s</li>" % esc(txt))
        else:
            out.append("        <p>%s</p>" % esc(txt))
    if open_list:
        out.append("        </ul>")

    for v in videos:
        out.append('        <div class="vid"><iframe src="%s" title="%s" loading="lazy" '
                   'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
                   'allowfullscreen></iframe></div>' % (esc(v), esc(h1)))

    if faq:
        out.append('        <h2>Frequently asked questions</h2>')
        out.append('        <dl class="faq">')
        for q, a in faq:
            out.append("          <dt>%s</dt><dd>%s</dd>" % (esc(q), esc(a)))
        out.append("        </dl>")

    for img in images[1:]:
        out.append('        <figure><img src="%s%s" alt="%s" loading="lazy"></figure>'
                   % (rel(path), esc(img["path"]), esc(img["alt"] or h1)))

    crumbs = [("Home", "index.html"), (h1, None)]
    graph = [breadcrumbs(crumbs, path), {
        "@type": "Service", "name": h1, "description": desc,
        "serviceType": h1, "url": "%s/%s" % (SITE, path),
        "areaServed": [{"@type": "City", "name": c} for c in
                       ("Delhi", "Gurugram", "Noida", "Faridabad", "Ghaziabad", "Manesar")],
        "provider": {"@type": "LocalBusiness", "name": "SHOWMAQERS",
                     "telephone": PHONE, "url": SITE + "/"},
    }]
    if faq:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    for v in videos:
        graph.append({"@type": "VideoObject", "name": h1,
                      "description": desc, "embedUrl": v,
                      "thumbnailUrl": SITE + "/images/logo-mark.webp",
                      "uploadDate": "2024-01-01"})

    return path, shell(path, title, desc, crumbs, "\n".join(out),
                       {"@context": "https://schema.org", "@graph": graph},
                       images[0]["path"] if images else None)


def build_post(post):
    """One blog post, from blog-data.js."""
    path = "blog/%s.html" % post["s"]
    images = keep_images(post.get("i") or [])
    title = "%s — SHOWMAQERS" % post["t"]
    desc = unique_desc((post.get("x") or post["t"])[:300], post["t"])

    out = []
    if post.get("w"):
        out.append('        <time datetime="%s">%s</time>' % (esc(post["d"]), esc(post["w"])))
    out.append("        <h1>%s</h1>" % esc(post["t"]))
    if images:
        out.append('        <img class="hero-shot" src="../%s" alt="%s" width="1200" height="675">'
                   % (esc(images[0]["path"]), esc(post["t"])))
    open_list = False
    for kind, txt in post.get("b") or []:
        if kind == "li" and not open_list:
            out.append("        <ul>"); open_list = True
        if kind != "li" and open_list:
            out.append("        </ul>"); open_list = False
        if kind == "h":
            # blog-data.js records one heading level, not six, so unlike the
            # crawled pages there is nothing here to preserve
            out.append("        <h2>%s</h2>" % esc(txt))
        elif kind == "li":
            out.append("          <li>%s</li>" % esc(txt))
        else:
            out.append("        <p>%s</p>" % esc(txt))
    if open_list:
        out.append("        </ul>")
    for img in images[1:]:
        out.append('        <figure><img src="../%s" alt="%s" loading="lazy"></figure>'
                   % (esc(img["path"]), esc(post["t"])))

    crumbs = [("Home", "index.html"), ("Blog", "blog.html"), (post["t"], None)]
    graph = [breadcrumbs(crumbs, path), {
        "@type": "BlogPosting", "headline": post["t"], "description": desc,
        "datePublished": post.get("d"), "dateModified": post.get("d"),
        "mainEntityOfPage": "%s/%s" % (SITE, path),
        "image": ["%s/%s" % (SITE, i["path"]) for i in images] or None,
        "author": {"@type": "Organization", "name": "SHOWMAQERS"},
        "publisher": {"@type": "Organization", "name": "SHOWMAQERS",
                      "logo": {"@type": "ImageObject", "url": SITE + "/images/logo-mark.webp"}},
    }]
    graph[1] = {k: v for k, v in graph[1].items() if v is not None}
    return path, shell(path, title, desc, crumbs, "\n".join(out),
                       {"@context": "https://schema.org", "@graph": graph},
                       images[0]["path"] if images else None)


SECTIONS = [
    ("Blog", lambda p: p.startswith("blog/")),
    ("Games &amp; activities on rent", lambda p: "-on-rent" in p or "game" in p),
    ("Artists &amp; manpower", lambda p: p.startswith("hire-") or "-for-hire-" in p or "artist" in p),
    ("Décor &amp; planning", lambda p: "decorat" in p or "planner" in p or "decor" in p),
    ("Events we have run", lambda p: True),
]


def build_directory(paths, titles):
    """sitemap.html -- the human one. Every generated page is linked from
    here, so none of them is an orphan a crawler can only reach by guessing."""
    groups = {name: [] for name, _ in SECTIONS}
    for path in paths:
        for name, match in SECTIONS:
            if match(path):
                groups[name].append(path)
                break
    out = ['        <h1>Everything we do</h1>',
           '        <p>Every service, game, artist and article on this site, in one list.</p>',
           '        <div class="dirs">']
    for name, _ in SECTIONS:
        items = sorted(groups[name], key=lambda p: titles[p].lower())
        if not items:
            continue
        out.append('          <div class="dir"><h2>%s</h2><ul>' % name)
        for path in items:
            out.append('            <li><a href="%s">%s</a></li>' % (esc(path), esc(titles[path])))
        out.append("          </ul></div>")
    out.append("        </div>")

    crumbs = [("Home", "index.html"), ("All pages", None)]
    return shell("sitemap.html", "Everything we do — SHOWMAQERS",
                 "Every service, game, artist and article Showmaqers offers across Delhi, "
                 "Gurugram, Noida, Faridabad, Ghaziabad and Manesar, in one list.",
                 crumbs, "\n".join(out),
                 {"@context": "https://schema.org",
                  "@graph": [breadcrumbs(crumbs, "sitemap.html")]})


def main():
    posts = load_posts()
    posts_by_slug = {p["s"]: p for p in posts}
    written, titles = [], {}

    for post in posts:
        path, page = build_post(post)
        written.append((path, page)); titles[path] = post["t"]

    for entry in load_pages():
        built = build_scraped(entry, posts_by_slug)
        if built:
            path, page = built
            written.append((path, page)); titles[path] = entry["title"] or path

    # the hand-written hubs belong in the sitemap too
    hubs = {"index.html": "Wedding & event planners in Delhi NCR",
            "manpower.html": "Hire manpower & artists",
            "games.html": "Games & activities on rent",
            "blog.html": "Blog", "vendors.html": "Join as an artist",
            "sitemap.html": "Everything we do"}

    written.append(("sitemap.html",
                    build_directory([p for p, _ in written], titles)))

    for path, page in written:
        full = os.path.join(ROOT, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)

    urls = list(hubs) + [p for p, _ in written if p != "sitemap.html"]
    seen, lines = set(), ['<?xml version="1.0" encoding="UTF-8"?>',
                          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in urls:
        if path in seen:
            continue
        seen.add(path)
        pri = "1.0" if path == "index.html" else "0.8" if path in hubs else "0.6"
        loc = SITE + "/" + ("" if path == "index.html" else path)
        lines.append("  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>"
                     % (esc(loc), TODAY, pri))
    lines.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\nDisallow: /admin.html\n\nSitemap: %s/sitemap.xml\n" % SITE)

    print("wrote %d pages, sitemap.xml with %d urls, robots.txt" % (len(written), len(seen)))


if __name__ == "__main__":
    sys.exit(main())
