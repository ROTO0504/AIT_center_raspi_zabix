# Mail2AlertLight

Zabbix のアラートメールを Microsoft Graph API 経由で監視し、Raspberry Pi の LED・ブザーで障害レベルを通知するシステム。
Web ダッシュボードでリアルタイムにステータスを確認できる。

## 構成

| ファイル | 役割 |
| --- | --- |
| `start_system.py` | エントリーポイント（依存インストール → Flask + 監視起動） |
| `web_app.py` | Web ダッシュボード & REST API |
| `monitor_service.py` | メール取得 → 判定 → GPIO 制御のコアロジック |
| `graph_client.py` | Microsoft Graph API クライアント（MSAL） |
| `settings.py` | `.env` からの設定読み込み |
| `env_loader.py` | `.env` パーサー |
| `utils.py` | プラットフォーム検出 |
| `gpio_test.py` | GPIO 単体テスト用ツール |
| `test_mail_scenarios.py` | メール判定ロジックのシナリオテスト |
| `install_autostart.sh` | systemd 自動起動セットアップ |

## GPIO ピン配置

| GPIO | 用途 |
| --- | --- |
| 5 | ブザー |
| 6 | LED 緑 |
| 13 | LED 黄 |
| 26 | LED 赤 |
| 21 | ボタン |

## セットアップ

### 1. 依存インストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数

`.env.example` をコピーして `.env` を作成し、Azure の認証情報を設定する。

```bash
cp .env.example .env
```

必須項目:

- `APP_ID` — Azure アプリケーション ID
- `TENANT_ID` — Azure テナント ID
- `CLIENT_SECRET` — クライアントシークレット（2026/11/10 期限）
- `MAILBOX_USER` — 監視対象メールボックス

### 3. 起動

```bash
python start_system.py
```

オプション:

- `--skip-install` — 依存インストールを省略
- `--port 8081` — Web ポート指定（デフォルト: 8080）

### 4. 自動起動（systemd）

```bash
sudo bash install_autostart.sh
```

```bash
sudo systemctl status mail2alertlight   # 確認
sudo systemctl stop mail2alertlight     # 停止
sudo systemctl disable mail2alertlight  # 無効化
```

## 動作仕様

- `high` / `disaster` レベルのアラート検出 → 赤 LED 点灯 + ブザー 2 回
- 起動時 → 緑 LED 点滅
- ボタン押下 → LED 消灯 + ブザー 1 回（ステータスは維持）
- Web ダッシュボード: `http://<ラズパイIP>:8080`

## テスト

詳細は `テストコマンド.md` を参照。

```bash
python3 test_mail_scenarios.py --list           # シナリオ一覧
python3 test_mail_scenarios.py high_problem      # 個別実行
python3 gpio_test.py test-all                    # GPIO ハードウェアテスト
```
