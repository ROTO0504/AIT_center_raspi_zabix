#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="mail2alertlight"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ $EUID -ne 0 ]]; then
  echo "このスクリプトは sudo で実行してください。"
  echo "例: sudo bash ${SCRIPT_DIR}/install_autostart.sh"
  exit 1
fi

if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif [[ -x "${SCRIPT_DIR}/../.venv/bin/python" ]]; then
  PYTHON_BIN="${SCRIPT_DIR}/../.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || true)"
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 が見つかりません。"
  exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/start_system.py" ]]; then
  echo "${SCRIPT_DIR}/start_system.py が見つかりません。"
  exit 1
fi

cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=Mail2AlertLight Auto Start Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_BIN} ${SCRIPT_DIR}/start_system.py --skip-install
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}.service
systemctl restart ${SERVICE_NAME}.service

systemctl --no-pager --full status ${SERVICE_NAME}.service | head -n 20

echo
echo "設定完了: 次回起動時から自動で start_system.py が root 権限で起動します。"
echo "停止: sudo systemctl stop ${SERVICE_NAME}"
echo "無効化: sudo systemctl disable ${SERVICE_NAME}"
