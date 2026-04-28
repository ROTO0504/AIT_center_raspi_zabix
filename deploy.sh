#!/usr/bin/env bash
set -euo pipefail

RASPI_USER="raspi"
RASPI_HOST="192.168.1.109"
RASPI_PATH="/home/raspi/Desktop/Mail2AlertLight"
SERVICE_NAME="mail2alertlight"
LOCAL_REMOTE_GITHUB="origin"
LOCAL_REMOTE_GITEA="AIT-center-mac"
RASPI_REMOTE="AIT-center-mac"
BRANCH="main"

skip_push=0
no_deps=0
for arg in "$@"; do
  case "$arg" in
    --skip-push) skip_push=1 ;;
    --no-deps)   no_deps=1 ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--skip-push] [--no-deps]

  --skip-push   Mac → リモートへの push を省略する
  --no-deps     ラズパイで pip install を省略する
EOF
      exit 0
      ;;
    *)
      echo "未知のオプション: $arg" >&2
      exit 1
      ;;
  esac
done

cd "$(dirname "$0")"

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  echo "現在のブランチが ${BRANCH} ではありません(${current_branch})。中断します。" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "コミットされていない変更があります。先にコミットしてください。" >&2
  git status --short >&2
  exit 1
fi

if [[ $skip_push -eq 0 ]]; then
  echo "==> push to ${LOCAL_REMOTE_GITHUB}/${BRANCH}"
  git push "$LOCAL_REMOTE_GITHUB" "$BRANCH"
  echo "==> push to ${LOCAL_REMOTE_GITEA}/${BRANCH}"
  git push "$LOCAL_REMOTE_GITEA" "$BRANCH"
else
  echo "==> push をスキップ"
fi

deps_cmd=".venv/bin/pip install -r requirements.txt"
if [[ $no_deps -eq 1 ]]; then
  deps_cmd="echo 'skip pip install'"
fi

echo "==> ${RASPI_USER}@${RASPI_HOST} で更新を実行"
ssh -o StrictHostKeyChecking=accept-new "${RASPI_USER}@${RASPI_HOST}" bash -se <<EOF
set -euo pipefail
cd "${RASPI_PATH}"
git fetch ${RASPI_REMOTE}
git reset --hard ${RASPI_REMOTE}/${BRANCH}
${deps_cmd}
sudo systemctl restart ${SERVICE_NAME}
sudo systemctl --no-pager status ${SERVICE_NAME} | head -n 15
EOF

echo "==> 完了"
