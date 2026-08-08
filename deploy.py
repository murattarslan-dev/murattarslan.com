#!/usr/bin/env python3
"""dist/ klasörünü Cloudflare Workers static assets olarak deploy eder.

Kullanım:
    CLOUDFLARE_API_TOKEN=... python3 deploy.py
"""
import base64
import hashlib
import json
import mimetypes
import os
import sys
from pathlib import Path

import requests

API = "https://api.cloudflare.com/client/v4"
SCRIPT_NAME = "murattarslan-com"
DIST = Path(__file__).parent / "dist"

TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
if not TOKEN:
    sys.exit("CLOUDFLARE_API_TOKEN ortam değişkeni gerekli")

S = requests.Session()
S.headers["Authorization"] = f"Bearer {TOKEN}"


def die(resp, step):
    sys.exit(f"[{step}] HTTP {resp.status_code}: {resp.text[:800]}")


# 0) account id
r = S.get(f"{API}/accounts")
if not r.ok:
    die(r, "accounts")
accounts = r.json()["result"]
if not accounts:
    sys.exit("Token hiçbir hesaba erişemiyor")
ACCOUNT = accounts[0]["id"]
print(f"Hesap: {accounts[0].get('name', '?')} ({ACCOUNT})")

# 1) manifest
manifest = {}
files = {}
for f in DIST.rglob("*"):
    if not f.is_file():
        continue
    rel = "/" + f.relative_to(DIST).as_posix()
    content = f.read_bytes()
    b64 = base64.b64encode(content).decode()
    ext = f.suffix[1:] if f.suffix else ""
    h = hashlib.sha256((b64 + ext).encode()).hexdigest()[:32]
    manifest[rel] = {"hash": h, "size": len(content)}
    files[h] = (rel, b64, mimetypes.guess_type(f.name)[0] or "application/octet-stream")

print(f"{len(manifest)} dosya hazır")

# 2) upload session
r = S.post(f"{API}/accounts/{ACCOUNT}/workers/scripts/{SCRIPT_NAME}/assets-upload-session",
           json={"manifest": manifest})
if not r.ok:
    die(r, "upload-session")
res = r.json()["result"]
jwt = res.get("jwt")
buckets = res.get("buckets") or []
print(f"Yüklenecek bucket sayısı: {len(buckets)}")

# 3) upload buckets
completion = jwt if not buckets else None
for bucket in buckets:
    parts = []
    for h in bucket:
        rel, b64, mime = files[h]
        parts.append((h, (h, b64, mime)))
    r = requests.post(f"{API}/accounts/{ACCOUNT}/workers/assets/upload?base64=true",
                      headers={"Authorization": f"Bearer {jwt}"}, files=parts)
    if r.status_code not in (200, 201):
        die(r, "asset-upload")
    body = r.json()
    if body.get("result", {}).get("jwt"):
        completion = body["result"]["jwt"]
    print(f"  bucket yüklendi ({len(bucket)} dosya)")

if not completion:
    sys.exit("Completion token alınamadı")

# 4) deploy worker (assets-only)
metadata = {
    "assets": {
        "jwt": completion,
        "config": {
            "not_found_handling": "404-page",
            "html_handling": "auto-trailing-slash",
        },
    },
    "compatibility_date": "2026-08-01",
}
r = S.put(f"{API}/accounts/{ACCOUNT}/workers/scripts/{SCRIPT_NAME}",
          files={"metadata": (None, json.dumps(metadata), "application/json")})
if not r.ok:
    die(r, "deploy")
print("✓ Deploy tamam:", r.json()["result"].get("id", SCRIPT_NAME))
