import os
import threading

from flask import Flask, jsonify, render_template_string

from monitor_service import MailLightMonitor
from settings import Settings


HTML = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>zabixモニター</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 20px;
      background:#f7f7f9;
      color:#222;
      min-height: 100vh;
      box-sizing: border-box;
    }
    .card {
      background:#fff;
      border-radius:12px;
      padding:24px;
      width: 100%;
      min-height: calc(100vh - 40px);
      box-sizing: border-box;
      box-shadow:0 2px 10px rgba(0,0,0,.08);
    }
    h1 { margin-top:0; }
    .status { font-size: 36px; font-weight: 700; margin: 8px 0 20px; }
    .status.problem { color:#c62828; }
    .status.warning { color:#c62828; }
    .status.ok { color:#2e7d32; }
    .status.high { color:#c62828; }
    .status.normal { color:#2e7d32; }
    .status.resolved { color:#2e7d32; }
    .status.unknown, .status.error { color:#6d6d6d; }
    .startup-note {
      display: none;
      margin: 0 0 12px;
      padding: 8px 12px;
      border-radius: 8px;
      background: #e8f5e9;
      border: 1px solid #a5d6a7;
      color: #1b5e20;
      font-size: 14px;
      font-weight: 600;
    }
    .grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:14px; }
    .item { background:#fafafa; border:1px solid #ececec; border-radius:8px; padding:14px; }
    .label { font-size:12px; color:#666; }
    .val { font-size:18px; font-weight:600; word-break:break-word; }
    .button-item {
      display:flex;
      flex-direction:column;
      gap:10px;
    }
    .button-state-card {
      display:flex;
      flex-direction:column;
      gap:10px;
    }
    .button-state-badge {
      display:inline-flex;
      align-items:center;
      gap:10px;
      width:fit-content;
      min-height:52px;
      padding:10px 16px;
      border-radius:999px;
      border:1px solid #d8dbe1;
      background:#f3f4f6;
      font-size:20px;
      font-weight:700;
      color:#444;
    }
    .button-state-badge.pressed {
      background:#ffebee;
      border-color:#ef9a9a;
      color:#b71c1c;
      box-shadow:0 0 0 4px rgba(198,40,40,.08);
    }
    .button-state-badge.released {
      background:#e8f5e9;
      border-color:#a5d6a7;
      color:#1b5e20;
    }
    .button-state-badge.unknown {
      background:#f5f5f5;
      border-color:#d6d6d6;
      color:#666;
    }
    .button-state-dot {
      width:14px;
      height:14px;
      border-radius:50%;
      background:currentColor;
      box-shadow:0 0 0 6px rgba(255,255,255,.45);
      flex:0 0 auto;
    }
    .button-state-sub {
      font-size:13px;
      line-height:1.5;
      color:#555;
      font-weight:600;
    }
    .row {
      display:grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap:20px;
      margin-top:12px;
    }
    .led-card { width:100%; text-align:center; }
    .led-dot {
      width:68px;
      height:68px;
      border-radius:50%;
      margin:0 auto 10px;
      border:2px solid #bbb;
      background:#ddd;
      box-shadow: inset 0 0 0 2px rgba(255,255,255,.45);
    }
    .led-label { font-size:16px; color:#444; margin-bottom:4px; font-weight: 600; }
    .led-state { font-size:14px; color:#666; }
    .led-dot.on.green { background:#2e7d32; border-color:#1b5e20; }
    .led-dot.on.yellow { background:#f9a825; border-color:#f57f17; }
    .led-dot.on.buzzer { background:#6a1b9a; border-color:#4a148c; }
    .led-dot.on.red { background:#c62828; border-color:#8e0000; }
    .led-dot.off { background:#e0e0e0; border-color:#bdbdbd; }
    .hosts { margin-top: 16px; }
    .host-list {
      display:grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap:12px;
    }
    .host-card {
      border:1px solid #e4e4e4;
      border-radius:10px;
      padding:12px;
      background:#fcfcfc;
    }
    .host-card.problem {
      background:#ffebee;
      border-color:#ef9a9a;
    }
    .host-top {
      display:flex;
      align-items:center;
      justify-content:space-between;
      margin-bottom:8px;
      gap:10px;
    }
    .host-name { font-size:16px; font-weight:700; }
    .host-status { font-size:12px; font-weight:700; }
    .host-status.problem { color:#c62828; }
    .host-status.warning { color:#a65b00; }
    .host-status.ok { color:#2e7d32; }
    .host-status.unknown { color:#6d6d6d; }
    .host-meta { font-size:12px; color:#555; margin:3px 0; }
    .toolbar { margin-top: 16px; }
    .btn {
      border: 1px solid #cfd3d8;
      background: #fff;
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      font-size: 14px;
    }
    .log-section { margin-top: 20px; }
    .log-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      font-family: ui-monospace, SFMono-Regular, monospace;
    }
    .log-table th {
      text-align: left;
      font-size: 11px;
      color: #888;
      padding: 4px 8px;
      border-bottom: 1px solid #e4e4e4;
    }
    .log-table td {
      padding: 4px 8px;
      border-bottom: 1px solid #f0f0f0;
      vertical-align: top;
    }
    .log-table tr:hover td { background: #fafafa; }
    .log-level-INFO { color: #1565c0; font-weight: 700; }
    .log-level-WARN { color: #e65100; font-weight: 700; }
    .log-level-ERROR { color: #c62828; font-weight: 700; }
    .modal {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.35);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 999;
    }
    .modal.show { display: flex; }
    .modal-card {
      width: min(520px, calc(100vw - 24px));
      background: #fff;
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,.25);
    }
    .modal-header {
      display:flex;
      align-items:center;
      justify-content:space-between;
      margin-bottom: 10px;
    }
    .gpio-table {
      width:100%;
      border-collapse: collapse;
      font-size:14px;
    }
    .gpio-table th, .gpio-table td {
      border-bottom:1px solid #ececec;
      padding:8px 6px;
      text-align:left;
    }
    .state-on { color:#2e7d32; font-weight:700; }
    .state-off { color:#8a8a8a; font-weight:700; }

    @media (max-width: 900px) {
      body { padding: 12px; }
      .card { min-height: calc(100vh - 24px); padding: 16px; }
      .status { font-size: 28px; }
      .grid { grid-template-columns: 1fr; }
      .row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .led-dot { width:56px; height:56px; }
      .host-list { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>zabix状態モニター</h1>
    <div id="startupNote" class="startup-note">起動中: 緑点滅で初回判定を待機しています。</div>
    <div id="status" class="status">loading...</div>
    <div class="grid">
      <div class="item"><div class="label">原因</div><div id="reason" class="val">-</div></div>
      <div class="item"><div class="label">判定更新時刻</div><div id="updated" class="val">-</div></div>
      <div class="item"><div class="label">対象メール件名</div><div id="subject" class="val">-</div></div>
      <div class="item"><div class="label">対象メール受信時刻</div><div id="received" class="val">-</div></div>
      <div class="item button-item">
        <div class="label">ボタン状態</div>
        <div class="button-state-card">
          <div id="buttonStateBadge" class="button-state-badge unknown">
            <span class="button-state-dot"></span>
            <span id="buttonStateText">確認中</span>
          </div>
          <div id="buttonStateSub" class="button-state-sub">-</div>
        </div>
      </div>
      <div class="item"><div class="label">最終押下時刻</div><div id="buttonLast" class="val">-</div></div>
    </div>
    <h3>ライト</h3>
    <div class="row" id="leds"></div>

    <div class="hosts">
      <h3>ホスト状態</h3>
      <div class="host-list" id="hosts"></div>
    </div>

    <div class="toolbar">
      <button id="openGpio" class="btn" type="button">GPIOステータス</button>
    </div>

    <div class="log-section">
      <h3>ログ</h3>
      <table class="log-table">
        <thead>
          <tr><th>時刻</th><th>レベル</th><th>メッセージ</th></tr>
        </thead>
        <tbody id="logRows"></tbody>
      </table>
    </div>
  </div>

  <div id="gpioModal" class="modal" role="dialog" aria-modal="true">
    <div class="modal-card">
      <div class="modal-header">
        <h3 style="margin:0;">GPIOステータス</h3>
        <button id="closeGpio" class="btn" type="button">閉じる</button>
      </div>
      <div id="gpioAvailable" class="label" style="margin-bottom:8px;">-</div>
      <table class="gpio-table">
        <thead>
          <tr><th>名前</th><th>GPIO</th><th>状態</th></tr>
        </thead>
        <tbody id="gpioRows"></tbody>
      </table>
    </div>
  </div>

  <script>
    function renderLed(name, on, key) {
      const wrap = document.createElement('div');
      wrap.className = 'led-card';

      const dot = document.createElement('div');
      dot.className = 'led-dot ' + (on ? 'on ' + key : 'off');

      const label = document.createElement('div');
      label.className = 'led-label';
      label.textContent = name;

      const state = document.createElement('div');
      state.className = 'led-state';
      state.textContent = on ? 'ON' : 'OFF';

      wrap.appendChild(dot);
      wrap.appendChild(label);
      wrap.appendChild(state);
      return wrap;
    }

    function overallLabel(value) {
      const labels = {
        high: '問題あり',
        normal: '正常',
        unknown: '未判定',
        error: 'エラー',
      };
      return labels[value] || value || '未判定';
    }

    function hostStatusLabel(value) {
      const labels = {
        problem: '問題あり',
        warning: '警告',
        ok: '正常',
        unknown: '未判定',
      };
      return labels[value] || value || '未判定';
    }

    let latestData = {};

    function renderGpioModal(data) {
      const gpio = data.gpio_status || {};
      const available = !!gpio.available;
      const pins = gpio.pins || {};
      const outputs = gpio.outputs || {};

      document.getElementById('gpioAvailable').textContent =
        available ? 'GPIO利用可能: はい' : 'GPIO利用可能: いいえ（表示のみ）';

      const rows = document.getElementById('gpioRows');
      rows.innerHTML = '';
      ['red'].forEach((name) => {
        const tr = document.createElement('tr');

        const tdName = document.createElement('td');
        tdName.textContent = name.toUpperCase();
        tr.appendChild(tdName);

        const tdPin = document.createElement('td');
        tdPin.textContent = String(pins[name] ?? '-');
        tr.appendChild(tdPin);

        const tdState = document.createElement('td');
        const on = !!outputs[name];
        tdState.textContent = on ? 'ON' : 'OFF';
        tdState.className = on ? 'state-on' : 'state-off';
        tr.appendChild(tdState);

        rows.appendChild(tr);
      });

      const buttonTr = document.createElement('tr');

      const buttonName = document.createElement('td');
      buttonName.textContent = 'BUTTON';
      buttonTr.appendChild(buttonName);

      const buttonPin = document.createElement('td');
      buttonPin.textContent = String(gpio.button_pin ?? '-');
      buttonTr.appendChild(buttonPin);

      const buttonState = document.createElement('td');
      if (gpio.button_pressed === true) {
        buttonState.textContent = 'PRESSED';
        buttonState.className = 'state-on';
      } else if (gpio.button_pressed === false) {
        buttonState.textContent = 'RELEASED';
        buttonState.className = 'state-off';
      } else {
        buttonState.textContent = '-';
        buttonState.className = 'state-off';
      }
      buttonTr.appendChild(buttonState);

      rows.appendChild(buttonTr);
    }

    async function refresh() {
      const res = await fetch('/api/status', { cache: 'no-store' });
      const data = await res.json();
      latestData = data;

      const statusEl = document.getElementById('status');
      statusEl.textContent = overallLabel(data.overall);
      statusEl.className = 'status ' + (data.overall || 'unknown');

      const startupNote = document.getElementById('startupNote');
      if (data.startup_blinking) {
        startupNote.style.display = 'block';
      } else {
        startupNote.style.display = 'none';
      }

      document.getElementById('reason').textContent = data.reason || '-';
      document.getElementById('updated').textContent = data.updated_at || '-';
      document.getElementById('subject').textContent = data.mail_subject || '-';
      document.getElementById('received').textContent = data.mail_received_at || '-';

      const buttonStatus = data.button_status || {};
      const configured = !!buttonStatus.configured;
      const silenced = !!buttonStatus.silenced;
      const pressedNow = !!buttonStatus.is_pressed;
      const buttonStateBadge = document.getElementById('buttonStateBadge');
      const buttonStateText = document.getElementById('buttonStateText');
      const buttonStateSub = document.getElementById('buttonStateSub');
      let buttonBadgeClass = 'button-state-badge unknown';
      let buttonMainText = '未設定';
      let buttonSubText = 'ボタン入力は未設定です';

      if (configured) {
        buttonMainText = pressedNow ? '押されています' : '押されていません';
        buttonBadgeClass = pressedNow
          ? 'button-state-badge pressed'
          : 'button-state-badge released';
        buttonSubText = 'PIN ' + (buttonStatus.pin ?? '-') +
          ' / pull-' + (buttonStatus.pull || '-') +
          (silenced ? ' / 消灯中' : ' / 通常');
      }

      buttonStateBadge.className = buttonBadgeClass;
      buttonStateText.textContent = buttonMainText;
      buttonStateSub.textContent = buttonSubText;
      document.getElementById('buttonLast').textContent =
        buttonStatus.last_pressed_at || '-';

      const leds = document.getElementById('leds');
      leds.innerHTML = '';
      const values = data.leds || {};
      leds.appendChild(renderLed('BUZZER', !!values.buzzer, 'buzzer'));
      leds.appendChild(renderLed('RED', !!values.red, 'red'));

      const hosts = document.getElementById('hosts');
      hosts.innerHTML = '';
      const hostStates = data.host_states || {};
      const hostMetrics = data.host_metrics || {};
      const entries = Object.entries(hostStates);
      if (entries.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'host-card';
        empty.textContent = 'ホスト状態なし';
        hosts.appendChild(empty);
      } else {
        entries.forEach(([host, st]) => {
          const metric = hostMetrics[host] || {};
          const card = document.createElement('div');
          card.className = 'host-card';
          if (st === 'problem') {
            card.classList.add('problem');
          }

          const top = document.createElement('div');
          top.className = 'host-top';

          const name = document.createElement('div');
          name.className = 'host-name';
          name.textContent = host;

          const status = document.createElement('div');
          status.className = 'host-status ' + st;
          status.textContent = hostStatusLabel(st);

          top.appendChild(name);
          top.appendChild(status);
          card.appendChild(top);

          const ip = document.createElement('div');
          ip.className = 'host-meta';
          ip.textContent = 'IP: ' + (metric.host_ip || '-');
          card.appendChild(ip);

          const severity = document.createElement('div');
          severity.className = 'host-meta';
          severity.textContent = 'Severity: ' + (metric.severity || '-');
          card.appendChild(severity);

          const started = document.createElement('div');
          started.className = 'host-meta';
          started.textContent = 'Problem開始: ' + (metric.problem_started_at || '-');
          card.appendChild(started);

          const resolved = document.createElement('div');
          resolved.className = 'host-meta';
          resolved.textContent = '最終復旧: ' + (metric.last_resolved_at || '-');
          card.appendChild(resolved);

          const recov = document.createElement('div');
          recov.className = 'host-meta';
          recov.textContent = '復旧時間: ' + (metric.last_recovery_text || '-');
          card.appendChild(recov);

          const ongoing = document.createElement('div');
          ongoing.className = 'host-meta';
          ongoing.textContent = '継続時間: ' + (metric.ongoing_problem_text || '-');
          card.appendChild(ongoing);

          const eventRow = document.createElement('div');
          eventRow.className = 'host-meta';
          eventRow.textContent = '最終イベント: ' + (metric.last_event_received_at || '-');
          card.appendChild(eventRow);

          hosts.appendChild(card);
        });
      }
    }

    const modal = document.getElementById('gpioModal');
    document.getElementById('openGpio').addEventListener('click', () => {
      renderGpioModal(latestData || {});
      modal.classList.add('show');
    });
    document.getElementById('closeGpio').addEventListener('click', () => {
      modal.classList.remove('show');
    });
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('show');
      }
    });

    async function refreshLogs() {
      const res = await fetch('/api/logs', { cache: 'no-store' });
      const logs = await res.json();
      const tbody = document.getElementById('logRows');
      tbody.innerHTML = '';
      logs.forEach((entry) => {
        const tr = document.createElement('tr');
        const tdAt = document.createElement('td');
        tdAt.textContent = entry.at;
        tr.appendChild(tdAt);
        const tdLevel = document.createElement('td');
        tdLevel.textContent = entry.level;
        tdLevel.className = 'log-level-' + entry.level;
        tr.appendChild(tdLevel);
        const tdMsg = document.createElement('td');
        tdMsg.textContent = entry.msg;
        tr.appendChild(tdMsg);
        tbody.appendChild(tr);
      });
    }

    refresh();
    refreshLogs();
    setInterval(refresh, 500);
    setInterval(refreshLogs, 2000);
  </script>
</body>
</html>
"""


def create_app() -> Flask:
    settings = Settings.from_env()
    monitor = MailLightMonitor(settings)

    app = Flask(__name__)

    poller = threading.Thread(
        target=monitor.run_forever,
        args=(settings.mail_poll_interval,),
        daemon=True,
    )
    poller.start()

    @app.get("/")
    def index():
        return render_template_string(HTML)

    @app.get("/api/status")
    def api_status():
        return jsonify(monitor.get_state())

    @app.get("/api/logs")
    def api_logs():
        return jsonify(monitor.get_logs())

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("WEB_PORT") or "8080")
    app.run(host="0.0.0.0", port=port)
