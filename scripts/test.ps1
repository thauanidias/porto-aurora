param([switch]$E2E)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "Falha: $Step" } }
if (-not (Test-Path -LiteralPath '.env')) { python scripts/init-env.py; Check-Exit 'Configuração' }
docker compose config --quiet
Check-Exit 'Compose'
docker compose build backend frontend
Check-Exit 'Imagens'
docker compose up -d --wait postgres redis
Check-Exit 'PostgreSQL e Redis'
docker compose -f docker-compose.yml -f docker-compose.e2e.yml run --rm --no-deps -v "${PWD}/backend:/app" -v "${PWD}/scripts:/scripts:ro" backend python /scripts/init-test-db.py
Check-Exit 'Banco de teste'
docker compose -f docker-compose.yml -f docker-compose.e2e.yml run --rm --no-deps -v "${PWD}/backend:/app" -v "${PWD}/scripts:/scripts:ro" backend python /scripts/verify-migrations.py
Check-Exit 'Migrations em banco limpo'
docker compose -f docker-compose.yml -f docker-compose.e2e.yml run --rm --no-deps -v "${PWD}/backend:/app" e2e-backend ruff check .
Check-Exit 'Lint backend'
docker compose -f docker-compose.yml -f docker-compose.e2e.yml run --rm --no-deps -v "${PWD}/backend:/app" e2e-backend mypy app --config-file pyproject.toml
Check-Exit 'Tipos backend'
docker compose -f docker-compose.yml -f docker-compose.e2e.yml run --rm --no-deps -v "${PWD}/backend:/app" e2e-backend python -m pytest -q
Check-Exit 'Testes backend'
npm.cmd ci --prefix frontend --cache .npm-cache
Check-Exit 'Dependências frontend'
npm.cmd run typecheck --prefix frontend
Check-Exit 'Tipos frontend'
npm.cmd run lint --prefix frontend
Check-Exit 'Lint frontend'
npm.cmd run test --prefix frontend
Check-Exit 'Testes frontend'
npm.cmd run build --prefix frontend
Check-Exit 'Build frontend'
if ($E2E) {
    docker compose -f docker-compose.yml -f docker-compose.e2e.yml run --rm --no-deps -v "${PWD}/scripts:/scripts:ro" -v "${PWD}/frontend:/e2e" e2e-backend python /scripts/prepare-e2e.py
    Check-Exit 'Usuário de teste'
    docker compose --profile local-testing -f docker-compose.yml -f docker-compose.e2e.yml up -d --wait mailpit e2e-backend e2e-worker e2e-web
    Check-Exit 'Portal de teste'
    $env:PLAYWRIGHT_BASE_URL='http://localhost:5189'
    $env:PLAYWRIGHT_EXTERNAL_SERVER='true'
    if (Test-Path -LiteralPath 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe') { $env:PLAYWRIGHT_CHANNEL='msedge' }
    npm.cmd run e2e --prefix frontend
    Check-Exit 'Navegador'
}
Write-Host 'Todas as verificações solicitadas passaram.'
