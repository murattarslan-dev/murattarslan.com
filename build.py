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


def reading_time(text: str) -> int:
    words = len(re.findall(r"\w+", text))
    return max(1, round(words / 200))


def load_posts():
    posts = []
    for f in sorted((CONTENT / "posts").glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        if meta.get("draft"):
            continue
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
                     "type": "article", "date_iso": p["date_iso"], "tags": p["tags"]})
    render("hakkimda.html", "hakkimda/index.html",
           page={"url": "/hakkimda/", "title": "Hakkımda", "description": "Murat Arslan kimdir?"})
    render("projeler.html", "projeler/index.html",
           page={"url": "/projeler/", "title": "Projeler", "description": "Geliştirdiğim projeler"})
    render("404.html", "404.html",
           page={"url": "/404", "title": "Sayfa bulunamadı", "description": "404"})

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

    # --- Sitemap ---
    urls = ["/", "/blog/", "/hakkimda/", "/projeler/"] + [p["url"] for p in posts]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"  <url><loc>{site['url']}{u}</loc></url>")
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    # --- robots.txt ---
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {site['url']}/sitemap.xml\n", encoding="utf-8")

    print(f"✓ {len(posts)} yazı, {len(urls)} sayfa -> dist/")


if __name__ == "__main__":
    main()
