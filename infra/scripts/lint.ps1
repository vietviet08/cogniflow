Set-Location api
ruff check app tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location ../web
npm run lint
