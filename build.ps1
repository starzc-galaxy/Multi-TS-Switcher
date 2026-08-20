$ErrorActionPreference = "Stop"
Write-Host "==> 创建虚拟环境"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
Write-Host "==> 安装依赖"
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
Write-Host "==> 生成垫片文件"
& ".venv\Scripts\python.exe" tools\generate_filler.py
Write-Host "==> 运行测试"
& ".venv\Scripts\python.exe" -m pytest -q
Write-Host "==> PyInstaller 打包"
& ".venv\Scripts\pyinstaller.exe" --noconfirm --clean MultiTS_Switcher.spec
Write-Host "完成：dist\MultiTS_Switcher\MultiTS_Switcher.exe"
