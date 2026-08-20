# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["tools/license_generator.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["cryptography"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "pyinstaller", "av", "PyQt6.QtSvg"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LicenseGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/icons/app_license.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="LicenseGenerator",
)
