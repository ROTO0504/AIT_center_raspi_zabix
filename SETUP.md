# 環境

- uv を使用しています
- start_system.py が本体です
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
cd /home/raspi/Desktop/Mail2AlertLight
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

## Mac → ラズパイ デプロイ

通常のデプロイは Mac リポジトリルートで `./deploy.sh` を実行する。
`origin`(GitHub) と `AIT-center-mac`(Gitea) の両方に push 後、SSH でラズパイの
`/home/raspi/Desktop/Mail2AlertLight` を `AIT-center-mac/main` に reset し、
`pip install` と `systemctl restart mail2alertlight` まで実行する。

```bash
./deploy.sh                  # 通常
./deploy.sh --skip-push      # push 済みのときラズパイ更新だけ実行
./deploy.sh --no-deps        # requirements.txt 変更がないと分かっているとき
```

ラズパイ側のローカル変更は `git reset --hard` で破棄されるため、
**ラズパイ上で直接コードを編集する運用は禁止**(常に Mac 側でコミット → デプロイ)。

デプロイ反映の確認は Web ダッシュボード `http://192.168.1.109:8080/` 内
「動作中バージョン」項目で行う。Mac の `git rev-parse --short HEAD` と
ハッシュが一致していればOK。

### 初回セットアップ(ラズパイ側で1度だけ)

1. リポジトリ clone(既にあれば不要)

   ```bash
   cd /home/raspi/Desktop
   git clone http://192.168.1.201:3000/admin/center_zabbix_beacon.git Mail2AlertLight
   cd Mail2AlertLight
   git remote rename origin AIT-center-mac
   ```

2. `.venv` 作成 + 依存インストール

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. `.env` を配置(`.env.example` 参照)

4. systemd 登録

   ```bash
   sudo bash install_autostart.sh
   ```

5. sudoers 設定(`raspi` がパスワードなしで `systemctl restart` できるようにする)

   ```bash
   sudo visudo -f /etc/sudoers.d/mail2alertlight
   ```

   内容:

   ```
   raspi ALL=(ALL) NOPASSWD: /bin/systemctl restart mail2alertlight, /bin/systemctl status mail2alertlight
   ```

### 初回セットアップ(Mac 側で1度だけ)

ラズパイへのSSH鍵を登録する。

```bash
ssh-copy-id raspi@192.168.1.109
```
