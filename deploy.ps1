# murattarslan.com - deploys dist/ to Cloudflare Workers (Windows PowerShell)
# Usage: run  .\deploy.ps1  in this folder, paste your API token when asked.
$ErrorActionPreference = "Stop"

$API = "https://api.cloudflare.com/client/v4"
$SCRIPT_NAME = "murattarslan-com"
$DIST = Join-Path $PSScriptRoot "dist"

if (-not (Test-Path $DIST)) { Write-Error "dist/ folder not found."; exit 1 }

$tok = Read-Host "Cloudflare API token"
$H = @{ Authorization = "Bearer $tok" }

$MIME = @{ ".html"="text/html"; ".css"="text/css"; ".js"="application/javascript";
  ".svg"="image/svg+xml"; ".png"="image/png"; ".jpg"="image/jpeg"; ".xml"="application/xml";
  ".txt"="text/plain"; ".json"="application/json"; ".ico"="image/x-icon"; ".webp"="image/webp" }

# 0) account
$acc = (Invoke-RestMethod -Headers $H "$API/accounts").result[0]
Write-Host ("Account: " + $acc.name)

# 1) manifest
$sha = [System.Security.Cryptography.SHA256]::Create()
$manifest = @{}
$files = @{}
Get-ChildItem $DIST -Recurse -File | ForEach-Object {
  $rel = "/" + $_.FullName.Substring($DIST.Length + 1).Replace("\", "/")
  $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
  $b64 = [Convert]::ToBase64String($bytes)
  $ext = $_.Extension.TrimStart(".")
  $hashBytes = $sha.ComputeHash([System.Text.Encoding]::ASCII.GetBytes($b64 + $ext))
  $hash = (($hashBytes | ForEach-Object { $_.ToString("x2") }) -join "").Substring(0, 32)
  $manifest[$rel] = @{ hash = $hash; size = $bytes.Length }
  $m = $MIME[$_.Extension.ToLower()]; if (-not $m) { $m = "application/octet-stream" }
  $files[$hash] = @{ b64 = $b64; mime = $m }
}
Write-Host ("Files ready: " + $manifest.Count)

# 2) upload session
$body = @{ manifest = $manifest } | ConvertTo-Json -Depth 5
$res = (Invoke-RestMethod -Method Post -Headers $H -ContentType "application/json" `
  -Body $body "$API/accounts/$($acc.id)/workers/scripts/$SCRIPT_NAME/assets-upload-session").result
$jwt = $res.jwt
$buckets = @($res.buckets)
Write-Host ("Buckets to upload: " + $buckets.Count)

# 3) upload buckets
$completion = $null
if ($buckets.Count -eq 0) { $completion = $jwt }
foreach ($bucket in $buckets) {
  $boundary = [System.Guid]::NewGuid().ToString()
  $sb = New-Object System.Text.StringBuilder
  foreach ($h in $bucket) {
    [void]$sb.Append("--$boundary`r`n")
    [void]$sb.Append("Content-Disposition: form-data; name=`"$h`"; filename=`"$h`"`r`n")
    [void]$sb.Append("Content-Type: " + $files[$h].mime + "`r`n`r`n")
    [void]$sb.Append($files[$h].b64)
    [void]$sb.Append("`r`n")
  }
  [void]$sb.Append("--$boundary--`r`n")
  $up = Invoke-RestMethod -Method Post -Headers @{ Authorization = "Bearer $jwt" } `
    -ContentType "multipart/form-data; boundary=$boundary" -Body $sb.ToString() `
    "$API/accounts/$($acc.id)/workers/assets/upload?base64=true"
  if ($up.result.jwt) { $completion = $up.result.jwt }
  Write-Host ("  bucket uploaded (" + $bucket.Count + " files)")
}
if (-not $completion) { Write-Error "No completion token received"; exit 1 }

# 4) deploy (assets-only worker)
$metadata = @{
  assets = @{
    jwt = $completion
    config = @{ not_found_handling = "404-page"; html_handling = "auto-trailing-slash" }
  }
  compatibility_date = "2026-08-01"
} | ConvertTo-Json -Depth 5
$boundary = [System.Guid]::NewGuid().ToString()
$mb = "--$boundary`r`nContent-Disposition: form-data; name=`"metadata`"`r`nContent-Type: application/json`r`n`r`n$metadata`r`n--$boundary--`r`n"
$dep = Invoke-RestMethod -Method Put -Headers $H `
  -ContentType "multipart/form-data; boundary=$boundary" -Body $mb `
  "$API/accounts/$($acc.id)/workers/scripts/$SCRIPT_NAME"
Write-Host "OK - deploy complete! https://murattarslan.com"