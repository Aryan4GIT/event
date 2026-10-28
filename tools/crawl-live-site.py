#!/usr/bin/env python
"""Crawl showmaqers.com and keep everything it finds.

  python tools/crawl-live-site.py pages     # every page -> showmaqers-site.json
  python tools/crawl-live-site.py images    # every picture -> images/live/
  python tools/crawl-live-site.py all       # both, in that order

This replaces showmaqers-content.json, which was a thinner pass: it flattened
every heading, paragraph and list item into one list of strings, so the
structure had to be guessed back afterwards, and it kept only the image URLs,
which is why 1037 of the 1139 pictures it named were never on disk and the
rebuilt pages came out text-rich and picture-poor.

What this one keeps per page: the final URL after redirects, the title, the
meta description, the canonical, every heading WITH ITS LEVEL, every
paragraph and list item IN DOCUMENT ORDER, every image with its alt text and
its position in the page, every YouTube link, every outbound link and every
internal one. Blocks are tagged, so the page builder lays out an <h2> as a
heading and an <li> as a list item instead of making everything a <p>.

It is the one site crawler here, so it is the place to change if the source
site moves or grows.
"""

import json
import os
import re
import sys
import time
from collections import deque, Counter
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = "https://showmaqers.com/"
HOSTS = {"showmaqers.com", "www.showmaqers.com"}
OUT = os.path.join(ROOT, "showmaqers-site.json")
IMG_DIR = os.path.join(ROOT, "images", "live")
UA = {"User-Agent": "Mozilla/5.0 (compatible; showmaqers-site-rebuild/1.0)"}
PAUSE = 0.25                     # the site is the client's own; still, be polite
TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote")
YT = re.compile(r"(?:youtube\.com|youtu\.be)", re.I)
# the phone numbers sit in <h?> tags in the old header, so they arrive as headings
JUNK = re.compile(r"^\s*(call\s*:|\+?91[\d\s\-]{8,}|\s*$)", re.I)


def bare(host):
    return host.lower().split(":")[0][4:] if host.lower().startswith("www.") else host.lower().split(":")[0]


def same_site(url):
    return bare(urlparse(url).netloc) in {bare(h) for h in HOSTS}


def clean(url):
    """One canonical spelling per page.

    The site answers on both showmaqers.com and www.showmaqers.com, and links
    to itself with both, so without this every page is fetched twice: the
    first run of this crawler came back with 296 pages for a 148 page site.
    Pin the host, drop the fragment, drop a bare '?' and drop the trailing
    slash so /x/ and /x are one page.
    """
    url = urldefrag(url)[0]
    if url.endswith("?"):
        url = url[:-1]
    if not same_site(url):
        return url                 # someone else's URL: leave it exactly as it is
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return "https://www.showmaqers.com%s%s" % (path, ("?" + p.query) if p.query else "")


def seeds():
    """Start from the home page, the live sitemap if there is one, and every
    URL the earlier scrape already knew about, so nothing that was reachable
    then can be missed now just because a link was dropped."""
    found = [START]
    for name in ("sitemap.xml", "sitemap_index.xml", "wp-sitemap.xml"):
        try:
            r = requests.get(START + name, headers=UA, timeout=20)
            if r.ok and "<" in r.text:
                found += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
        except requests.RequestException:
            pass
    old = os.path.join(ROOT, "showmaqers-content.json")
    if os.path.exists(old):
        with open(old, encoding="utf-8") as f:
            found += [e["url"] for e in json.load(f)]
    out, seen = [], set()
    for u in found:
        u = clean(u)
        if same_site(u) and u not in seen and not u.lower().endswith(".xml"):
            seen.add(u); out.append(u)
    return out


def scrape(html, url):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    body = []
    for el in soup.find_all(TEXT_TAGS):
        txt = " ".join(el.get_text(" ", strip=True).split())
        if not txt or JUNK.match(txt) or len(txt) < 2:
            continue
        kind = "li" if el.name in ("li",) else ("h" if el.name[0] == "h" else "p")
        if body and body[-1][1] == txt:        # the theme repeats some headings
            continue
        body.append([kind, txt, el.name])

    images = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if img.get("srcset"):
            src = img["srcset"].split(",")[-1].strip().split(" ")[0] or src
        if not src or src.startswith("data:"):
            continue
        images.append({"src": urljoin(url, src),
                       "alt": " ".join((img.get("alt") or "").split())})

    youtube = []
    for el in soup.find_all(["iframe", "a", "source"]):
        link = el.get("src") or el.get("href") or ""
        if link and YT.search(link):
            youtube.append(urljoin(url, link))

    links = [clean(urljoin(url, a["href"])) for a in soup.find_all("a", href=True)]
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    desc = soup.find("meta", attrs={"name": "description"})

    return {
        "url": url,
        "title": (soup.title.get_text(strip=True) if soup.title else ""),
        "description": (desc.get("content") or "").strip() if desc else "",
        "canonical": canon.get("href") if canon else "",
        "headings": [t for k, t, _ in body if k == "h"],
        "body": body,
        "images": images,
        "youtube": sorted(set(youtube)),
        "links": sorted({l for l in links if same_site(l)}),
        "external": sorted({l for l in links if not same_site(l)
                            and l.startswith("http")}),
    }


SUSPECT = re.compile("\u00c2[\\s\u00a0]|\u00e2\u20ac|\u00c3[\u00a9\u00a8\u00a1]|\u00f0\u0178|\u011f\u0178")


MANGLED = re.compile("[ðğ][Ÿ][-ÿğŸ� -⁯]{0,3}")


def unmangle(text):
    """Undo double-encoded text that arrives that way from the source.

    Five pages -- the newer blog posts, the ones written with emoji -- store
    their copy already mangled: UTF-8 bytes that were once read as a single
    byte encoding and re-encoded as UTF-8. They render as garbage on
    showmaqers.com too, so this is not a crawl bug to work around but
    damage to repair: "Letâ€™s" back to "Let's", "ğŸŒ¸" back to the flower.
    Encode back to the byte string and decode it as what it always was.
    latin-1 first, then the two Windows code pages that also map 0x80-0x9f,
    and keep the attempt only if it actually leaves fewer bad sequences.
    """
    # U+FFFD is a byte the source already lost; it can only ever print as a
    # black diamond, so it goes whether or not the rest needs repairing.
    if "�" in text:
        text = " ".join(text.replace("�", "").split())
    if not SUSPECT.search(text):
        return text
    best, score = text, len(SUSPECT.findall(text))
    for codec in ("latin-1", "cp1252", "cp1254"):
        try:
            cand = text.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        hits = len(SUSPECT.findall(cand))
        if hits < score:
            best, score = cand, hits
    if score:
        # What is left is damage the source cannot be read back from: a byte
        # was already replaced with U+FFFD before we ever saw the page, so the
        # emoji it belonged to is gone. Drop the wreckage rather than print it
        # -- a missing flower reads better than "gY..." in the middle of a
        # sentence. Only mangled-emoji runs match; ordinary text cannot.
        best = MANGLED.sub("", best).replace("�", "")
        best = " ".join(best.split())
    return best


def dedupe_and_strip(pages):
    """Collapse the two spellings of each page, then drop the site chrome.

    Chrome is found by counting, not by naming selectors: the nav, the footer
    menu, the "WE PROVIDE OUR SERVICES IN THE FOLLOWING CITIES" list and the
    three phone numbers are whatever text turns up on more than half the
    pages. 49 blocks go that way and 2100 of real copy stay. Naming the
    theme's classes instead would break the next time the theme changes.
    """
    by_path = {}
    for page in pages:
        by_path.setdefault(urlparse(page["url"]).path.rstrip("/") or "/", page)
    uniq = list(by_path.values())

    seen = Counter()
    for page in uniq:
        for kind, txt, tag in page["body"]:
            seen[txt] += 1
    chrome = {t for t, c in seen.items() if c > len(uniq) * 0.5}

    for page in uniq:
        page["title"] = unmangle(page["title"])
        page["description"] = unmangle(page["description"])
        page["body"] = [[k, unmangle(t), tag]
                        for k, t, tag in page["body"] if t not in chrome]
        page["headings"] = [unmangle(h) for h in page["headings"] if h not in chrome]
        # one canonical spelling per picture, same reason as for pages
        out, got = [], set()
        for img in page["images"]:
            path = urlparse(img["src"]).path
            if path not in got:
                got.add(path)
                img["src"] = "https://www.showmaqers.com" + path
                out.append(img)
        page["images"] = out
        # ?wmode=opaque and ?t=94 are the same video twice
        vids, ids = [], set()
        for y in page["youtube"]:
            m = re.search(r"(?:embed/|v=|youtu\.be/)([A-Za-z0-9_-]{6,})", y)
            key = m.group(1) if m else y
            if key not in ids:
                ids.add(key)
                vids.append(y)
        page["youtube"] = vids
    return uniq, sorted(chrome)


def crawl_pages():
    queue, seen, pages, failed = deque(seeds()), set(), [], []
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, headers=UA, timeout=30)
        except requests.RequestException as e:
            failed.append([url, str(e)[:120]]); continue
        if not r.ok or "html" not in r.headers.get("content-type", ""):
            failed.append([url, "status %s" % r.status_code]); continue
        # The server sends no charset in the header, so requests falls back to
        # ISO-8859-1 while the page itself declares UTF-8 in a meta tag. Left
        # alone, every curly quote and non-breaking space arrives as mojibake
        # -- "FaridabadA A Greater" -- and gets written into 148 pages.
        if "charset" not in r.headers.get("content-type", "").lower():
            r.encoding = r.apparent_encoding or "utf-8"
        page = scrape(r.text, clean(r.url))
        page["fetched_from"] = url
        pages.append(page)
        for link in page["links"]:
            if link not in seen and not re.search(
                    r"\.(jpe?g|png|gif|webp|svg|pdf|zip|mp4|css|js)$", link, re.I):
                queue.append(link)
        print("%4d/%-4d %s  (%d blocks, %d img, %d yt)"
              % (len(pages), len(pages) + len(queue), page["url"][:78],
                 len(page["body"]), len(page["images"]), len(page["youtube"])),
              flush=True)
        time.sleep(PAUSE)

    pages, chrome = dedupe_and_strip(pages)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"crawled": time.strftime("%Y-%m-%d"), "start": START,
                   "chrome": chrome, "pages": pages, "failed": failed}, f,
                  ensure_ascii=False, indent=1)
    yt = {y for p in pages for y in p["youtube"]}
    imgs = {i["src"] for p in pages for i in p["images"]}
    print("\npages %d  failed %d  distinct images %d  distinct youtube %d"
          % (len(pages), len(failed), len(imgs), len(yt)))
    for y in sorted(yt):
        print("   ", y)


def crawl_images():
    with open(OUT, encoding="utf-8") as f:
        data = json.load(f)
    urls = sorted({i["src"] for p in data["pages"] for i in p["images"]})
    os.makedirs(IMG_DIR, exist_ok=True)
    got = skipped = bad = 0
    total_bytes = 0
    for n, url in enumerate(urls, 1):
        name = os.path.basename(urlparse(url).path) or "img-%d" % n
        name = re.sub(r"[^A-Za-z0-9._-]", "-", name)[:120]
        dest = os.path.join(IMG_DIR, name)
        if os.path.exists(dest) and os.path.getsize(dest):
            skipped += 1; continue
        try:
            r = requests.get(url, headers=UA, timeout=45)
            if not r.ok or not r.content:
                bad += 1; continue
            with open(dest, "wb") as f:
                f.write(r.content)
            got += 1; total_bytes += len(r.content)
        except requests.RequestException:
            bad += 1
        if n % 25 == 0:
            print("  %4d/%d  got %d  skipped %d  failed %d  %.1fMB"
                  % (n, len(urls), got, skipped, bad, total_bytes / 1e6), flush=True)
        time.sleep(0.05)
    print("images: %d downloaded, %d already here, %d failed, %.1fMB"
          % (got, skipped, bad, total_bytes / 1e6))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what == "clean":                      # re-do the tidy-up without re-crawling
        with open(OUT, encoding="utf-8") as f:
            data = json.load(f)
        data["pages"], data["chrome"] = dedupe_and_strip(data["pages"])
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print("%d pages kept, %d chrome blocks dropped"
              % (len(data["pages"]), len(data["chrome"])))
        sys.exit()
    if what in ("pages", "all"):
        crawl_pages()
    if what in ("images", "all"):
        crawl_images()
