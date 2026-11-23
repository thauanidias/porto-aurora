$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
docker version
if ($LASTEXITCODE -ne 0) { throw 'Inicie o Docker Desktop antes de continuar.' }
if (-not (Test-Path -LiteralPath '.env')) {
    python scripts/init-env.py
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar configuração.' }
}
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Configuração Docker inválida.' }
$composeArgs = @()
if (Select-String -LiteralPath '.env' -Pattern '^TEST_EMAIL_ENABLED=true\s*$' -Quiet) {
    $composeArgs = @('--profile', 'local-testing')
}
docker compose @composeArgs up -d --build --wait
if ($LASTEXITCODE -ne 0) { throw 'Falha na inicialização. Consulte docker compose logs.' }
docker compose exec -T nginx nginx -t
if ($LASTEXITCODE -ne 0) { throw "Configuração Nginx inválida." }
docker compose exec -T nginx nginx -s reload
if ($LASTEXITCODE -ne 0) { throw "Falha ao recarregar Nginx." }
if (Select-String -LiteralPath '.env' -Pattern '^RESUME_AI_ENABLED=true\s*$' -Quiet) {
    $resumeModelLine = Get-Content -LiteralPath '.env' | Where-Object { $_ -match '^RESUME_AI_MODEL=' } | Select-Object -Last 1
    $resumeModelName = if ($resumeModelLine) { ($resumeModelLine -split '=', 2)[1].Trim() } else { 'qwen2.5:3b' }
    docker compose exec -T resume-ai ollama show $resumeModelName 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        docker compose exec -T resume-ai ollama pull $resumeModelName
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar o modelo local de leitura de curriculos.' }
    }
}
Write-Host 'Portal: http://localhost:8088'
Write-Host 'Crie o primeiro administrador: docker compose exec backend python -m app.bootstrap'
