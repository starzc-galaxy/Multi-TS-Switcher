"""一键交付打包：Cython 源码防护 → 主程序/测试工具/授权工具分别打包 → 使用说明书 → 7-Zip 压缩。

参考 D:\\AircraftDetect2\\cython_utils.py 的做法：
复制工程 → 逐文件 cythonize -i → 清理 .py/.c → 在受保护目录内用 spec（.pyd 作为 binaries、
pathex='.'、显式 hiddenimports）分别打包 → 7-Zip 压缩。
"""

import ast
import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VENV = ROOT / ".venv"
PY = VENV / "Scripts" / "python.exe"
PROTECTED = ROOT / "build" / "protected"
DELIVER = ROOT / "交付"

from app.version import APP_VERSION  # noqa: E402

SEVEN_ZIP_CANDIDATES = [
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
]

QT_HIDDEN = [
    "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtSvg", "PyQt6.sip",
]
STDLIB_HIDDEN = [
    "atexit", "argparse", "base64", "codecs", "collections", "collections.abc",
    "concurrent.futures", "contextlib", "copy", "csv", "ctypes", "dataclasses",
    "datetime", "encodings", "encodings.utf_8", "faulthandler", "functools",
    "glob", "hashlib", "importlib.metadata", "importlib.resources", "importlib.util",
    "inspect", "io", "itertools", "json", "locale", "logging", "logging.handlers",
    "multiprocessing", "multiprocessing.queues", "multiprocessing.shared_memory",
    "os", "pathlib", "pickle", "platform", "queue", "re", "shutil", "signal",
    "socket", "struct", "subprocess", "sys", "tempfile", "threading", "time",
    "traceback", "typing", "uuid", "warnings", "weakref", "xml", "xml.etree",
    "xml.etree.ElementTree", "zipfile",
]
THIRD_HIDDEN = [
    "av", "numpy", "psutil",
    "cryptography", "cryptography.exceptions",
    "cryptography.hazmat", "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.serialization",
    "cryptography.hazmat.primitives.asymmetric",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
]
EXCLUDES = [
    "pytest", "pyinstaller", "setuptools", "pip", "wheel", "tkinter",
    "unittest", "PIL", "lxml", "docx", "cython",
]


def sh(cmd, cwd=None):
    print("  ->", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, check=True)


def py_run(args, cwd=None):
    return subprocess.run([str(PY)] + [str(a) for a in args], cwd=str(cwd) if cwd else None,
                          check=True, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def collect_top_imports(paths) -> set[str]:
    mods: set[str] = set()
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        files += [p] if p.is_file() else list(p.rglob("*.py"))
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    mods.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
    return {m for m in mods if m not in ("__future__", "app", "tools")}


def should_exclude_dir(path: Path, exclude_dirs) -> bool:
    name = path.name
    for d in exclude_dirs:
        if d.endswith("*") and name.startswith(d[:-1]):
            return True
        if d.startswith("*") and name.endswith(d[1:]):
            return True
        if d in name or name == d:
            return True
    return False


def copy_with_exclude(src: Path, dst: Path, exclude_dirs) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        s = src / item.name
        d = dst / item.name
        if s.is_file():
            shutil.copy2(s, d)
        elif s.is_dir():
            if should_exclude_dir(s, exclude_dirs):
                print(f"  跳过目录: {s.name}")
                continue
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d)


def find_py_files(dir_path: Path, exclude_dirs) -> list[Path]:
    out: list[Path] = []
    for item in dir_path.iterdir():
        if item.is_file() and item.suffix == ".py":
            out.append(item)
        elif item.is_dir() and not should_exclude_dir(item, exclude_dirs):
            out.extend(find_py_files(item, exclude_dirs))
    return out


def cythonize_src(src: Path, dst: Path, exclude_files, exclude_dirs, keep_files) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    copy_with_exclude(src, dst, exclude_dirs)
    targets = []
    for f in find_py_files(dst, exclude_dirs):
        rel = str(f.relative_to(dst)).replace("\\", "/")
        if rel in keep_files or any(rel.endswith(k) or rel == k for k in exclude_files):
            continue
        targets.append(f)
    if targets:
        sh([VENV / "Scripts" / "cythonize.exe", "-i", "-3", "--parallel", "4"]
           + [str(t) for t in targets])
    missing = [t for t in targets
               if not any(p.suffix == ".pyd" and p.name.startswith(t.stem + ".")
                          for p in t.parent.iterdir())]
    if missing:
        raise RuntimeError(f"Cython 编译失败（未生成 .pyd）: {[str(m) for m in missing]}")
    # 清理：删除已编译 .py（保留 keep/exclude 与 __init__.py）与 .c
    for p in dst.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        rel = str(p.relative_to(dst)).replace("\\", "/")
        if rel in keep_files or any(rel.endswith(k) or rel == k for k in exclude_files):
            continue
        p.unlink()
    for c in dst.rglob("*.c"):
        c.unlink()


def collect_pyd_files(root: Path) -> list[tuple[str, str]]:
    out = []
    seen = set()
    for pyd in root.rglob("*.pyd"):
        rel = pyd.relative_to(root)
        if any(part in ("build", "dist", "__pycache__", ".git") for part in rel.parts):
            continue
        if str(pyd) in seen:
            continue
        seen.add(str(pyd))
        target = "." if rel.parent == Path(".") else str(rel.parent).replace("\\", "/")
        out.append((str(pyd), target))
    return out


def write_version_info(name: str, version: str, out: Path) -> None:
    parts = [int(x) for x in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    ver = "(" + ", ".join(str(p) for p in parts) + ")"
    descs = {
        "MultiTS_Switcher": "Multi-TS Switcher - 多路 UDP-TS 轮询切换转发系统",
        "TestTool": "Multi-TS Switcher 生产测试工具",
        "LicenseGenerator": "Multi-TS Switcher 授权生成器",
    }
    desc = descs.get(name, name)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={ver}, prodvers={ver}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('080404b0', [
    StringStruct('CompanyName', 'Multi-TS Switcher'),
    StringStruct('FileDescription', '{desc}'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', '{name}'),
    StringStruct('OriginalFilename', '{name}.exe'),
    StringStruct('ProductName', 'Multi-TS Switcher'),
    StringStruct('ProductVersion', '{version}')])]),
  VarFileInfo([VarStruct('Translation', [2052, 1200])])]
)
"""
    out.write_text(text, encoding="utf-8")


def write_spec(name: str, entry: str, datas: list[tuple[str, str]], icon: str,
               hidden: list[str], root: Path) -> None:
    datas = list(datas)
    # .pyd 作为 binaries 打入后，包结构需要 __init__.py 才能正常导入
    for init in root.rglob("__init__.py"):
        rel = init.relative_to(root)
        if any(part in ("build", "dist", "__pycache__") for part in rel.parts):
            continue
        target = str(rel.parent).replace("\\", "/") or "."
        datas.append((str(init), target))
    datas_repr = "[" + ", ".join(f"({a!r}, {b!r})" for a, b in datas) + "]"
    hidden_repr = "[" + ", ".join(repr(h) for h in hidden) + "]"
    spec = f"""# -*- mode: python ; coding: utf-8 -*-
import glob, os

def collect_pyd_files(root_dir):
    pyd_files = []
    seen = set()
    for pyd_file in glob.glob(os.path.join(root_dir, '**', '*.pyd'), recursive=True):
        if not os.path.isfile(pyd_file) or not pyd_file.endswith('.pyd'):
            continue
        rel_check = os.path.relpath(pyd_file, root_dir).replace('\\\\', '/')
        if any(f'/{{s}}/' in f'/{{rel_check}}/' for s in ['build', 'dist', '__pycache__', '.git']):
            continue
        if pyd_file in seen:
            continue
        seen.add(pyd_file)
        rel_path = os.path.relpath(pyd_file, root_dir)
        target = os.path.dirname(rel_path) or '.'
        pyd_files.append((pyd_file, target))
    return pyd_files

additional_binaries = collect_pyd_files(r'.')
hiddenimports = {hidden_repr}

a = Analysis(
    [{entry!r}],
    pathex=['.'],
    binaries=additional_binaries,
    datas={datas_repr},
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={EXCLUDES!r},
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name={name!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon={icon!r},
    version={name!r} + '_version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name={name!r},
)
"""
    (root / f"{name}.spec").write_text(spec, encoding="utf-8")


def find_7zip() -> Path:
    for p in SEVEN_ZIP_CANDIDATES:
        if os.path.isfile(p):
            return Path(p)
    raise FileNotFoundError("未找到 7-Zip（请安装到 C:\\Program Files\\7-Zip\\）")


def build_manual_and_icons() -> None:
    DELIVER.mkdir(parents=True, exist_ok=True)
    old = DELIVER / "使用说明书.docx"
    if old.exists():
        try:
            old.unlink()
        except PermissionError:
            pass
    py_run([ROOT / "tools" / "build_manual.py", DELIVER / "使用说明书.docx"])
    py_run([ROOT / "tools" / "generate_icons.py"])


def prepare_protected() -> None:
    if PROTECTED.exists():
        shutil.rmtree(PROTECTED)
    PROTECTED.mkdir(parents=True, exist_ok=True)
    exclude_dirs = ["build", "dist", "__pycache__", ".git", ".venv", "docs",
                    "tests", ".pytest_cache", "交付", ".idea"]
    print("[1/6] Cython 源码防护")
    cythonize_src(ROOT / "app", PROTECTED / "app", ["main.py"], exclude_dirs, {"main.py"})
    tools_exclude = [
        "build_pipeline.py", "build_manual.py", "collect_imports.py",
        "generate_filler.py", "generate_test_sources.py", "generate_icons.py",
        "make_license.py",
    ]
    cythonize_src(ROOT / "tools", PROTECTED / "tools", tools_exclude, exclude_dirs, set())
    # 入口统一放在 launchers/，删除受保护树中 app/main.py
    (PROTECTED / "app" / "main.py").unlink(missing_ok=True)
    copy_with_exclude(ROOT / "assets", PROTECTED / "assets", exclude_dirs)
    if (ROOT / "test_sources").exists():
        shutil.copytree(ROOT / "test_sources", PROTECTED / "test_sources",
                        dirs_exist_ok=True)
    (PROTECTED / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "app.json", PROTECTED / "config" / "app.json")
    shutil.copy2(ROOT / "config" / "groups.json", PROTECTED / "config" / "groups.json")
    launchers = PROTECTED / "launchers"
    launchers.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "app" / "main.py", launchers / "main.py")
    wrapper = (
        "import os, sys, traceback\n\n"
        "def _run():\n"
        "    try:\n"
        "        from app.debuglog import install_excepthook\n"
        "        install_excepthook()\n"
        "        from {module} import main\n"
        "        raise SystemExit(main())\n"
        "    except SystemExit:\n"
        "        raise\n"
        "    except Exception:\n"
        "        try:\n"
        "            log = os.path.join(os.path.dirname(sys.executable), 'startup_error.log')\n"
        "            with open(log, 'a', encoding='utf-8') as fh:\n"
        "                fh.write(traceback.format_exc())\n"
        "        except Exception:\n"
        "            pass\n"
        "        raise\n\n"
        'if __name__ == "__main__":\n'
        "    _run()\n"
    )
    (launchers / "run_stream_tester.py").write_text(
        wrapper.format(module="tools.stream_tester"), encoding="utf-8")
    (launchers / "run_license_generator.py").write_text(
        wrapper.format(module="tools.license_generator"), encoding="utf-8")
    leftover = [p for p in (PROTECTED / "app").rglob("*.py") if p.name != "__init__.py"]
    if leftover:
        raise RuntimeError(f"源码防护不完整，仍有未编译 .py: {leftover}")
    print("    防护完成，.pyd 数量:", len(collect_pyd_files(PROTECTED)))


def collect_hidden(root: Path) -> list[str]:
    mods = collect_top_imports([root / "app", root / "tools" / "stream_tester.py",
                                root / "tools" / "license_generator.py"])
    return sorted(set(mods) | set(QT_HIDDEN) | set(STDLIB_HIDDEN))


def build_exes() -> None:
    print("[2/6] PyInstaller 分别打包")
    hidden = collect_hidden(PROTECTED)
    main_hidden = sorted(set(hidden) | set(THIRD_HIDDEN))
    test_hidden = main_hidden
    lic_third = [m for m in THIRD_HIDDEN if m not in ("av", "numpy")]
    lic_hidden = sorted(set(hidden) | set(lic_third))

    specs = [
        ("MultiTS_Switcher", "launchers/main.py",
         [("assets", "assets"), ("config", "config")],
         "assets/icons/app_multits.ico", main_hidden),
        ("TestTool", "launchers/run_stream_tester.py",
         [("assets", "assets"), ("test_sources", "test_sources")],
         "assets/icons/app_testtool.ico", test_hidden),
        ("LicenseGenerator", "launchers/run_license_generator.py",
         [], "assets/icons/app_license.ico", lic_hidden),
    ]
    for name, entry, datas, icon, hidden_list in specs:
        write_version_info(name, APP_VERSION, PROTECTED / f"{name}_version_info.txt")
        write_spec(name, entry, datas, icon, hidden_list, PROTECTED)
        sh([VENV / "Scripts" / "pyinstaller.exe", "--clean", "--noconfirm",
            f"{name}.spec"], cwd=PROTECTED)


def collect_delivery() -> None:
    print("[3/6] 收集交付物")
    for n in ("MultiTS_Switcher", "TestTool", "LicenseGenerator"):
        src = PROTECTED / "dist" / n
        dst = DELIVER / n
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    # 授权生成器需要私钥才能签发授权文件（随授权工具一起交付，需整体保密）
    priv_src = PROTECTED / "tools" / "dev_private_key.pem"
    if priv_src.exists():
        shutil.copy2(priv_src, DELIVER / "LicenseGenerator" / "dev_private_key.pem")
        print("    已随授权工具携带私钥: dev_private_key.pem")


def compress() -> None:
    print("[4/6] 7-Zip 压缩")
    seven = find_7zip()
    manual = sorted(DELIVER.glob("使用说明书*.docx"), key=lambda p: p.stat().st_mtime)
    if not manual:
        raise FileNotFoundError("未找到使用说明书")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    arc = DELIVER / f"MultiTS_Switcher_V{APP_VERSION}_交付包_{stamp}.7z"
    if arc.exists():
        arc.unlink()
    release_note = DELIVER / "版本说明.txt"
    release_note.write_text(
        f"Multi-TS Switcher V{APP_VERSION}\n"
        f"发布日期：{datetime.now():%Y-%m-%d}\n\n"
        "包含程序：\n"
        "  MultiTS_Switcher.exe   主程序（多组 UDP-TS 轮询切换转发与监控）\n"
        "  TestTool.exe           生产测试工具（发送测试源/接收验证）\n"
        "  LicenseGenerator.exe   授权生成器（管理员用，含私钥，请妥善保管）\n"
        "  使用说明书.docx        用户手册\n\n"
        "授权说明：离线授权，机器码绑定；授权组数 1-9，可设有效期。\n"
        "注意事项：\n"
        "  1. 授权生成器内附私钥，等于签发权，请只交给授权管理员；\n"
        "  2. 组与组之间请勿复用同一个组播地址；\n"
        "  3. 多网卡环境请在组配置中显式选择绑定网卡。\n",
        encoding="utf-8")
    cmd = [str(seven), "a", "-t7z", "-mx=5", str(arc),
           str(DELIVER / "MultiTS_Switcher"), str(DELIVER / "TestTool"),
           str(DELIVER / "LicenseGenerator"), str(manual[-1]), str(release_note)]
    subprocess.run(cmd, check=True)
    print("交付包:", arc)


def main() -> None:
    print("=" * 60)
    print("Multi-TS Switcher 一键交付打包")
    print("=" * 60)
    print("[0/6] 运行测试")
    py_run(["-m", "pytest", "-q"])
    build_manual_and_icons()
    prepare_protected()
    build_exes()
    collect_delivery()
    compress()
    print("=" * 60)
    print("全部完成。")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
