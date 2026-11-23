$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose exec backend python -m app.bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Falha no bootstrap. Nenhuma credencial padrão foi definida.' }
