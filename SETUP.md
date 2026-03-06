# 環境

- uv を使用しています
- ver2/mailRead.py が本体メール確認ようです
- .env にて以下の値を設定してください
  - APP_ID
  - OBJECT_ID
  - TENANT_ID
  - CLIENT_SECRET
    - 2026/11/10 に期限切れ予定
  - MAILBOX_USER

## Raspberry Pi 起動時に自動実行する（root 権限）

`start_system.py` をラズパイ起動時に自動起動するには、`systemd` サービスを登録します。

```bash
cd /home/raspi/Desktop/Mail2AlertLight/ver2
sudo bash install_autostart.sh
```

確認:

```bash
sudo systemctl status mail2alertlight
```

停止:

```bash
sudo systemctl stop mail2alertlight
```

自動起動を無効化:

```bash
sudo systemctl disable mail2alertlight
```
