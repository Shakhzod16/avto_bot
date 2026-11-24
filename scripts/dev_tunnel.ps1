$ErrorActionPreference = "Continue"

$cloudflared = Get-Command "cloudflared" -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared topilmadi. O'rnatish: winget install --id Cloudflare.cloudflared"
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
if (-not (Test-Path $envPath)) {
    throw ".env topilmadi. Avval .env.example faylidan .env yarating."
}

$updatedUrl = $false
& $cloudflared.Source tunnel --url "http://127.0.0.1:8000" 2>&1 | ForEach-Object {
    $line = $_.ToString()
    Write-Host $line
    if (-not $updatedUrl -and $line -match '(https://[a-zA-Z0-9-]+\.trycloudflare\.com)') {
        $webappUrl = "$($Matches[1])/app/"
        $content = [System.IO.File]::ReadAllText($envPath)
        $setting = "WEBAPP_URL=$webappUrl"
        if ($content -match '(?m)^WEBAPP_URL=.*$') {
            $content = [regex]::Replace(
                $content,
                '(?m)^WEBAPP_URL=.*$',
                [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $setting }
            )
        } else {
            $content = $content.TrimEnd() + [Environment]::NewLine + $setting + [Environment]::NewLine
        }
        [System.IO.File]::WriteAllText(
            $envPath,
            $content,
            [System.Text.UTF8Encoding]::new($false)
        )
        $updatedUrl = $true
        Write-Host "WEBAPP_URL .env faylida yangilandi: $webappUrl"
        Write-Host "Tunnel ochiq tursin; backendni qayta ishga tushiring."
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "cloudflared tunnel xato bilan tugadi (exit code $LASTEXITCODE)."
}
if (-not $updatedUrl) {
    throw "cloudflared HTTPS trycloudflare.com manzilini bermadi."
}
