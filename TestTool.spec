# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["tools/stream_tester.py"],
    pathex=[],
    binaries=[],
    datas=[("test_sources", "test_sources")],
    hiddenimports=["av"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "pyinstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TestTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/icons/app_testtool.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="TestTool",
)
