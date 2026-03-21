Start-Process pwsh -ArgumentList "-NoExit", "-Command", "Set-Location api; uvicorn app.main:app --reload"
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "Set-Location web; npm run dev"
