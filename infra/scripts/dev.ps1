$apiCommand = "Set-Location api; `$env:WATCHFILES_FORCE_POLLING='true'; fastapi dev app/main.py --reload-dir app --reload-dir alembic"

Start-Process pwsh -ArgumentList "-NoExit", "-Command", $apiCommand
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "Set-Location web; npm run dev"
