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

## デプロイ(Gitea Actions による自動化)

`AIT-center-mac`(Gitea, http://192.168.1.201:3000) の `main` ブランチに push されると、
Gitea Actions の `deploy` ワークフロー(`.gitea/workflows/deploy.yml`)が走り、
ラズパイ上の self-hosted runner が `/home/raspi/Desktop/Mail2AlertLight` を
最新コミットに `git reset --hard` し、`pip install` と
`sudo systemctl restart mail2alertlight` まで実行する。

普段の運用は以下だけ:

```bash
git push AIT-center-mac main   # GitHub にも残す場合は `git push origin main` も
```

ラズパイ側のローカル変更は `git reset --hard` で破棄されるため、
**ラズパイ上で直接コードを編集する運用は禁止**(常に Mac 側でコミット → push)。

反映確認は Web ダッシュボード `http://192.168.1.109:8080/` の
「動作中バージョン」項目で行う。Mac の `git rev-parse --short HEAD` と
ハッシュが一致していればOK。

### 初回セットアップ(Gitea 側)

1. Gitea 管理画面で Actions を有効化
   - サイト管理 → 設定 → Actions: ON
   - リポジトリ `admin/center_zabbix_beacon` の Settings → Actions も ON
2. Runner 登録用トークンを発行
   - サイト管理 → Actions → Runners → 「Create runner token」

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

5. sudoers 設定(runner ユーザーがパスワードなしで `systemctl restart` できるようにする)

   ```bash
   sudo visudo -f /etc/sudoers.d/mail2alertlight
   ```

   内容:

   ```
   raspi ALL=(ALL) NOPASSWD: /bin/systemctl restart mail2alertlight, /bin/systemctl is-active mail2alertlight, /bin/systemctl status mail2alertlight
   ```

6. **act_runner**(Gitea Actions の self-hosted runner)を導入

   ```bash
   # ARM64 ラズパイ向けバイナリ(Pi 4/5)
   cd ~
   wget https://gitea.com/gitea/act_runner/releases/latest/download/act_runner-linux-arm64 -O act_runner
   chmod +x act_runner
   sudo mv act_runner /usr/local/bin/

   # 登録(ラベル `raspi` を付与してホスト実行モード)
   mkdir -p ~/act_runner && cd ~/act_runner
   act_runner register \
     --no-interactive \
     --instance http://192.168.1.201:3000 \
     --token <Gitea で発行した runner token> \
     --name raspi \
     --labels "raspi:host"
   ```

   → `~/act_runner/.runner` と `~/act_runner/config.yaml` が生成される。

7. systemd で runner を常駐化

   ```bash
   sudo tee /etc/systemd/system/act_runner.service >/dev/null <<'EOF'
   [Unit]
   Description=Gitea act_runner
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=raspi
   WorkingDirectory=/home/raspi/act_runner
   ExecStart=/usr/local/bin/act_runner daemon
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   EOF

   sudo systemctl daemon-reload
   sudo systemctl enable --now act_runner
   sudo systemctl status act_runner
   ```

   Gitea 管理画面 → Actions → Runners に `raspi (idle)` が出れば成功。

8. 動作確認: 適当に1コミット push し、Gitea のリポジトリ → Actions タブで
   `deploy` ワークフローが Success になり、ラズパイの Web UI 「動作中バージョン」
   が新しいハッシュに更新されることを確認。
