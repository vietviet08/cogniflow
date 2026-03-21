Set-Location api
pytest tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location ../web
npm run test
