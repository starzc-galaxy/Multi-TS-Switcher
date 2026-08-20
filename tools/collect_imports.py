"""扫描 .py 源码中的顶层 import，供 PyInstaller --hidden-import 使用（Cython 防护后模块图不可见）。"""

import ast
import sys
from pathlib import Path


def collect(path: Path) -> set[str]:
    mods: set[str] = set()
    files = [path] if path.is_file() else list(path.rglob("*.py"))
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    mods.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
    return mods


def main() -> int:
    skip = {"__future__", "app", "tools"}
    all_mods: set[str] = set()
    for arg in sys.argv[1:]:
        all_mods |= collect(Path(arg))
    for m in sorted(m for m in all_mods if m not in skip):
        print(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
