$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.env')) {
    python scripts/init-env.py
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar configuracao.' }
}
$envPath = Join-Path (Get-Location) '.env'
$content = [System.IO.File]::ReadAllText($envPath)
if ($content -match '(?m)^ENVIRONMENT=production\s*$') {
    throw 'O modo de testes nao pode ser ativado em producao.'
}
$content = [regex]::Replace($content, '(?m)^TEST_EMAIL_ENABLED=.*\r?\n?', '')
[System.IO.File]::WriteAllText($envPath, $content.TrimEnd() + "`nTEST_EMAIL_ENABLED=true`n", [System.Text.UTF8Encoding]::new($false))
& "$PSScriptRoot/start.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar o ambiente de testes.' }
Write-Host 'E-mails de teste: http://localhost:8025'
