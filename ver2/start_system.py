import argparse
import os
import subprocess
import sys
from pathlib import Path

from env_loader import load_env
from settings import Settings
from web_app import create_app


def _install_requirements() -> None:
    req = Path(__file__).with_name("requirements.txt")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req)])


def main() -> int:
    load_env(Path(__file__).with_name(".env"))

    parser = argparse.ArgumentParser(
        description="Zabbixメール監視 + Web表示 + GPIO + ボタン制御を一括起動"
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="requirements.txt のインストールをスキップ",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WEB_PORT") or 8080),
        help="Webポート (default: 8080)",
    )
    args = parser.parse_args()

    if not args.skip_install:
        print("[1/2] 依存パッケージを確認・インストールします...")
        _install_requirements()

    settings = Settings.from_env()

    print("[2/2] システム起動中...")
    print("  - メール受信監視")
    print(f"    polling interval: {settings.mail_poll_interval} sec")
    print("  - Web反映")
    print("  - GPIOライト/ブザー制御")
    print("  - ボタン監視（有効時）")

    app = create_app()
    app.run(host="0.0.0.0", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
