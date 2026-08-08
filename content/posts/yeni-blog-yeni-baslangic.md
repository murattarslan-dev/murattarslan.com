---
title: Yeni blog, yeni başlangıç
slug: yeni-blog-yeni-baslangic
date: 2026-08-08
description: murattarslan.com'u sıfırdan yeniledim — markdown tabanlı statik bir site, Cloudflare Workers üzerinde. İşte nasıl ve neden.
tags: [blog, cloudflare, python]
---

Bir süredir aklımdaydı: kendime düzenli yazabileceğim, hızlı ve bakımı kolay bir blog kurmak. Sonunda oturdum ve siteyi **sıfırdan** yeniledim.

## Neden statik site?

Blog dediğin şey aslında çok basit: yazılar, bir liste sayfası ve biraz stil. Bunun için koca bir framework taşımaya gerek yok. Statik sitenin avantajları:

- **Hız** — sunucuda hiçbir şey çalışmıyor, her sayfa hazır HTML.
- **SEO** — içerik doğrudan HTML'de, arama motorları için hazır.
- **Bakım** — veritabanı yok, güvenlik yaması yok, kırılacak şey yok.

## Nasıl çalışıyor?

Yazılar `content/posts/` klasöründe birer markdown dosyası. Küçük bir Python betiği bunları okuyup Jinja2 şablonlarıyla HTML'e çeviriyor:

```python
for f in (CONTENT / "posts").glob("*.md"):
    meta, body = parse_front_matter(f.read_text())
    html = markdown.markdown(body, extensions=["fenced_code"])
```

Çıktı `dist/` klasörüne gidiyor ve **Cloudflare Workers** static assets olarak yayınlanıyor. Dünyanın her yerinde, uçta (edge) sunuluyor — Türkiye'den de, Japonya'dan da milisaniyeler içinde açılıyor.

## Yeni yazı eklemek

Tek yapmam gereken yeni bir `.md` dosyası oluşturup deploy etmek:

```bash
python3 build.py && npx wrangler deploy
```

Bu kadar. Ne admin paneli, ne veritabanı, ne de karmaşık bir CI süreci.

## Sırada ne var?

Burada yazılım geliştirme üzerine öğrendiklerimi, karşılaştığım problemleri ve çözümlerini paylaşacağım. Takipte kal.
