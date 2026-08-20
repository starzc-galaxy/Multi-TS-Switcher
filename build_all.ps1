# ============================================================
# 一键交付打包（调用 Python 流水线 tools/build_pipeline.py）
# 用法: powershell -ExecutionPolicy Bypass -File build_all.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    Write-Host "创建虚拟环境..."
    python -m venv "$Root\.venv"
}
& "$Root\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check `
    -r "$Root\requirements.txt" cython python-docx
& "$Root\.venv\Scripts\python.exe" "$Root\tools\build_pipeline.py"
