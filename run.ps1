$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $playgroundPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $playgroundPython)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
        & $playgroundPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Could not install the playground dependencies.' }
    }
    Write-Host 'Open http://localhost:8501 after Streamlit starts. Press Ctrl+C to stop.'
    & $playgroundPython -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501
} finally {
    Pop-Location
}
