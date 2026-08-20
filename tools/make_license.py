"""签发授权文件：python tools/make_license.py <machine_id> <allowed_groups> [--out path] [--days N]"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.licensing.license_io import create_license, generate_keypair

PRIV_PATH = Path(__file__).parent / "dev_private_key.pem"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("machine_id")
    ap.add_argument("allowed_groups", type=int)
    ap.add_argument("--out", default="lic/device.lic")
    ap.add_argument("--days", type=int, default=0, help="有效天数，0=永久")
    ap.add_argument("--init-keys", action="store_true",
                    help="生成密钥对并回填公钥到 app/licensing/keys.py")
    args = ap.parse_args()
    if not PRIV_PATH.exists():
        priv, pub = generate_keypair()
        PRIV_PATH.write_bytes(priv)
        keys_py = Path(__file__).parent.parent / "app" / "licensing" / "keys.py"
        keys_py.write_text(f'PUBLIC_KEY_PEM = {pub!r}\n', encoding="utf-8")
        print(f"密钥已生成: {PRIV_PATH}")
    text = create_license(
        args.machine_id, args.allowed_groups, PRIV_PATH.read_bytes(),
        days=args.days or None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"授权已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
