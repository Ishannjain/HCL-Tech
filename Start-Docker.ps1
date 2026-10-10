$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$retailDockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $retailDockerBin) { $env:PATH = $retailDockerBin + ';' + $env:PATH }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop first.' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env'))) { throw 'Configure .env using .env.example first.' }
docker desktop start
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop could not start. Check its status window.' }
docker compose up --build -d --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed. Run docker compose logs api ui.' }
Write-Host 'Chatbot: http://127.0.0.1:8501/'
Write-Host 'API docs: http://127.0.0.1:8000/docs'
