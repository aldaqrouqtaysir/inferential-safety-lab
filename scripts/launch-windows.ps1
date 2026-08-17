Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Create .venv and install the project before launching. See README.md."
}
& $pythonExecutable -m streamlit run (Join-Path $repositoryRoot "streamlit_app.py")
