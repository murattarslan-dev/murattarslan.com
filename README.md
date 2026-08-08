# murattarslan.com

Markdown tabanlı statik blog — Cloudflare Workers (static assets) üzerinde.

## Klasör yapısı

```
site.yaml           → site ayarları (bio, sosyal linkler, projeler, yetenekler)
content/posts/*.md  → blog yazıları (front matter + markdown)
templates/          → Jinja2 HTML şablonları
static/             → CSS, favicon, OG görseli
build.py            → siteyi dist/ klasörüne derler
dist/               → yayınlanan çıktı (derlenmiş halde hazır)
```

## Yeni yazı ekleme

`content/posts/` altına yeni bir `.md` dosyası koy:

```markdown
---
title: Yazının başlığı
date: 2026-08-15
description: Kısa özet (SEO ve kartlarda görünür)
tags: [flutter, android]
---

Yazı içeriği...
```

Sonra derle + deploy et.

## Derleme (Python 3 gerekir)

```
pip install markdown jinja2 pyyaml
python build.py
```

Not: `dist/` klasörü zaten derlenmiş halde geliyor; içerik değiştirmediysen
tekrar derlemene gerek yok.

## Deploy — iki seçenek

**A) wrangler ile (Node.js varsa, önerilen):**

```
npx wrangler login    # ilk seferde, tarayıcıda onay verirsin
npx wrangler deploy
```

**B) PowerShell betiği ile (hiçbir kurulum gerektirmez):**

Proje klasöründe PowerShell aç:

```
.\deploy.ps1
```

Token soracak — dash.cloudflare.com → My Profile → API Tokens →
"Edit Cloudflare Workers" şablonuyla oluşturduğun token'ı yapıştır.

> Eğer "running scripts is disabled" hatası alırsan önce şunu çalıştır:
> `Set-ExecutionPolicy -Scope Process Bypass`
