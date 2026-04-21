"""ローカルでweb UIだけを試すための開発用サーバ。

GPIO や Microsoft Graph には一切繋がず、モックデータを返す。
起動: .venv/bin/python web_dev.py
ブラウザ: http://localhost:8080/
"""

import os
import random
from collections import deque
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template_string

from web_app import HTML


START_TIME = datetime.now()
LOGS = deque(maxlen=100)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _seed_logs() -> None:
    base = datetime.now() - timedelta(minutes=5)
    samples = [
        ("INFO", "監視サービス起動 (DEVモック)"),
        ("INFO", "メールフォルダ Inbox の購読を開始"),
        ("WARN", "ホスト app-02 が応答遅延 (mock)"),
        ("INFO", "ホスト app-02 が復旧 (mock)"),
        ("ERROR", "ホスト db-01 で問題検知 (mock)"),
    ]
    for i, (level, msg) in enumerate(samples):
        LOGS.append(
            {
                "at": (base + timedelta(seconds=i * 30)).isoformat(timespec="seconds"),
                "level": level,
                "msg": msg,
            }
        )


def _mock_state() -> dict:
    elapsed = (datetime.now() - START_TIME).total_seconds()
    cycle = int(elapsed // 10) % 3
    if cycle == 0:
        overall, reason = "normal", "問題なし (mock)"
        leds = {"green": True, "yellow": False, "buzzer": False, "red": False}
        host_states = {"web-01": "ok", "app-01": "ok", "db-01": "ok"}
    elif cycle == 1:
        overall, reason = "high", "ホスト db-01 で重大障害 (mock)"
        leds = {"green": False, "yellow": False, "buzzer": True, "red": True}
        host_states = {"web-01": "ok", "app-01": "warning", "db-01": "problem"}
    else:
        overall, reason = "unknown", "メール未受信 (mock)"
        leds = {"green": False, "yellow": True, "buzzer": False, "red": False}
        host_states = {"web-01": "ok", "app-01": "ok", "db-01": "unknown"}

    host_metrics = {
        host: {
            "host_ip": f"192.168.10.{10 + i}",
            "severity": {"problem": "High", "warning": "Average", "ok": "-", "unknown": "-"}[st],
            "problem_started_at": _now_iso() if st == "problem" else "-",
            "last_resolved_at": _now_iso() if st == "ok" else "-",
            "last_recovery_text": "00:01:23" if st == "ok" else "-",
            "ongoing_problem_text": "00:00:42" if st == "problem" else "-",
            "last_event_received_at": _now_iso(),
        }
        for i, (host, st) in enumerate(host_states.items())
    }

    return {
        "overall": overall,
        "reason": reason,
        "updated_at": _now_iso(),
        "mail_subject": f"[mock] alert cycle={cycle}",
        "mail_received_at": _now_iso(),
        "leds": leds,
        "host_states": host_states,
        "host_metrics": host_metrics,
        "gpio_status": {
            "available": False,
            "pins": {"green": 6, "yellow": 13, "buzzer": 5, "red": 26},
            "outputs": leds,
            "button_pin": 12,
            "button_pressed": random.choice([True, False, None]),
        },
        "startup_blinking": elapsed < 5,
        "button_status": {
            "configured": True,
            "pin": 12,
            "pull": "up",
            "is_pressed": False,
            "silenced": False,
            "last_pressed_at": "-",
        },
    }


def create_app() -> Flask:
    app = Flask(__name__)
    _seed_logs()

    @app.get("/")
    def index():
        return render_template_string(HTML)

    @app.get("/api/status")
    def api_status():
        return jsonify(_mock_state())

    @app.get("/api/logs")
    def api_logs():
        return jsonify(list(reversed(LOGS)))

    return app


if __name__ == "__main__":
    port = int(os.getenv("WEB_PORT") or "8080")
    create_app().run(host="127.0.0.1", port=port, debug=True)
