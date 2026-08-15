#!/usr/bin/env python3
"""murattarslan.com — minimal statik site üreteci.

Kullanım:
    python3 build.py          # content/ + templates/ + static/ -> dist/

Yazı eklemek için content/posts/ altına front matter'lı bir .md dosyası koy:

    ---
    title: Yazı başlığı
    date: 2026-08-08
    description: Kısa özet (SEO ve kartlarda görünür)
    tags: [flutter, android]
    ---
    Yazı içeriği markdown olarak...
"""
import re
import shutil
import struct
import html as htmllib
from datetime import datetime, date
from pathlib import Path

import yaml
import markdown
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"

MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slugify(text: str) -> str:
    text = text.translate(TR_MAP).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def fmt_date(d) -> str:
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return f"{d.day} {MONTHS_TR[d.month - 1]} {d.year}"


def parse_front_matter(text: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def md_render(text: str) -> str:
    return markdown.markdown(
        text,
        extensions=["fenced_code", "codehilite", "tables", "toc", "smarty"],
        extension_configs={
            "codehilite": {"guess_lang": False, "css_class": "highlight"},
            "toc": {"permalink": False},
        },
        output_format="html5",
    )


def image_size(url_path: str):
    """/assets/... yolundaki PNG veya JPEG'in (genislik, yukseklik) degerini dondurur.

    Ek bagimlilik istemedigimiz icin dosya basligini elle okuyoruz.
    Olcu cikarilamazsa None doner; sablon o zaman olcu yazmaz.
    """
    if not url_path.startswith("/assets/"):
        return None
    f = STATIC / url_path[len("/assets/"):]
    if not f.is_file():
        return None
    d = f.read_bytes()
    if d[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", d[16:24])
    if d[:2] == b"\xff\xd8":  # JPEG: SOFn markerini bul
        i = 2
        while i + 9 < len(d):
            if d[i] != 0xFF:
                i += 1
                continue
            marker = d[i + 1]
            if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if marker == 0xD9:
                break
            seg = struct.unpack(">H", d[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", d[i + 5:i + 9])
                return w, h
            i += 2 + seg
    return None


def reading_time(text: str) -> int:
    words = len(re.findall(r"\w+", text))
    return max(1, round(words / 200))


def load_posts():
    posts = []
    for f in sorted((CONTENT / "posts").glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        if meta.get("draft"):
            continue
        cover = meta.get("cover", "")
        cover_size = image_size(cover) if cover else None
        d = meta.get("date", date.today())
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        slug = meta.get("slug") or slugify(meta.get("title", f.stem))
        posts.append({
            "title": meta.get("title", f.stem),
            "date": d,
            "date_h": fmt_date(d),
            "date_iso": d.isoformat(),
            "description": meta.get("description", ""),
            "cover": cover,
            "cover_alt": meta.get("cover_alt", meta.get("title", "")),
            "cover_w": cover_size[0] if cover_size else None,
            "cover_h": cover_size[1] if cover_size else None,
            "tags": meta.get("tags", []),
            "slug": slug,
            "url": f"/blog/{slug}/",
            "html": md_render(body),
            "reading": reading_time(body),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def main():
    site = yaml.safe_load((ROOT / "site.yaml").read_text(encoding="utf-8"))
    site["about_html"] = md_render(site.get("about", ""))
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=False)
    env.globals["site"] = site
    env.globals["year"] = date.today().year

    posts = load_posts()
    all_tags = sorted({t for p in posts for t in p["tags"]})

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(STATIC, DIST / "assets")

    def render(template, out_path, **ctx):
        html_out = env.get_template(template).render(**ctx)
        out = DIST / out_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_out, encoding="utf-8")

    render("index.html", "index.html", posts=posts[:4],
           page={"url": "/", "title": None, "description": site["description"]})
    render("blog.html", "blog/index.html", posts=posts, all_tags=all_tags,
           page={"url": "/blog/", "title": "Blog", "description": "Tüm yazılar — " + site["title"]})
    for p in posts:
        render("post.html", f"blog/{p['slug']}/index.html", post=p,
               page={"url": p["url"], "title": p["title"], "description": p["description"],
                     "type": "article", "date_iso": p["date_iso"], "tags": p["tags"],
                     "image": p["cover"], "image_alt": p["cover_alt"],
                     "image_w": p["cover_w"], "image_h": p["cover_h"]})
    render("hakkimda.html", "hakkimda/index.html",
           page={"url": "/hakkimda/", "title": "Hakkımda", "description": "Murat Arslan kimdir?"})
    render("projeler.html", "projeler/index.html",
           page={"url": "/projeler/", "title": "Projeler", "description": "Geliştirdiğim projeler"})
    render("404.html", "404.html",
           page={"url": "/404", "title": "Sayfa bulunamadı", "description": "404", "noindex": True})

    # --- RSS ---
    items = []
    for p in posts[:20]:
        items.append(f"""  <item>
    <title>{htmllib.escape(p['title'])}</title>
    <link>{site['url']}{p['url']}</link>
    <guid>{site['url']}{p['url']}</guid>
    <pubDate>{p['date'].strftime('%a, %d %b %Y 09:00:00 +0300')}</pubDate>
    <description>{htmllib.escape(p['description'])}</description>
  </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{htmllib.escape(site['title'])}</title>
  <link>{site['url']}</link>
  <atom:link href="{site['url']}/rss.xml" rel="self" type="application/rss+xml"/>
  <description>{htmllib.escape(site['description'])}</description>
  <language>tr</language>
{chr(10).join(items)}
</channel>
</rss>
"""
    (DIST / "rss.xml").write_text(rss, encoding="utf-8")

    # --- Sitemap (lastmod destekli) ---
    latest = posts[0]["date_iso"] if posts else date.today().isoformat()
    entries = [("/", latest), ("/blog/", latest), ("/hakkimda/", latest),
               ("/projeler/", latest)] + [(p["url"], p["date_iso"]) for p in posts]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm in entries:
        sm.append(f"  <url><loc>{site['url']}{u}</loc><lastmod>{lm}</lastmod></url>")
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    # --- robots.txt ---
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {site['url']}/sitemap.xml\n", encoding="utf-8")

    print(f"✓ {len(posts)} yazı, {len(entries)} sayfa -> dist/")


if __name__ == "__main__":
    main()
