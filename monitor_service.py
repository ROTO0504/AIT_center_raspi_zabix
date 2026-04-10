import re
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

from graph_client import GraphClient
from settings import Settings


class LogBuffer:
    def __init__(self, maxlen: int = 300) -> None:
        self._entries: Deque[Dict[str, str]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def _add(self, level: str, message: str) -> None:
        entry = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "level": level,
            "msg": message,
        }
        with self._lock:
            self._entries.append(entry)

    def info(self, message: str) -> None:
        self._add("INFO", message)

    def warn(self, message: str) -> None:
        self._add("WARN", message)

    def error(self, message: str) -> None:
        self._add("ERROR", message)

    def get(self) -> List[Dict[str, str]]:
        with self._lock:
            return list(reversed(self._entries))


@dataclass
class LightState:
    overall: str
    reason: str
    updated_at: str
    mail_subject: str
    mail_received_at: str
    leds: Dict[str, bool]
    host_states: Dict[str, str]
    host_metrics: Dict[str, Dict[str, object]]
    gpio_status: Dict[str, object]
    startup_blinking: bool
    button_status: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class GpioLightController:
    def __init__(
        self,
        green_pin: int = 6,
        yellow_pin: int = 13,
        buzzer_pin: int = 5,
        red_pin: int = 26,
    ) -> None:
        self.pins = {
            "green": green_pin,
            "yellow": yellow_pin,
            "buzzer": buzzer_pin,
            "red": red_pin,
        }
        self._gpio = None
        self._enabled = False
        self._last_outputs = {
            "green": False,
            "yellow": False,
            "buzzer": False,
            "red": False,
        }
        self._startup_blink_stop = threading.Event()
        self._startup_blink_thread: Optional[threading.Thread] = None
        self._button_pin: Optional[int] = None
        self._button_pull = "up"
        self._init_error = ""
        self._button_error = ""
        self._init_gpio()

    def _init_gpio(self) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore

            self._gpio = GPIO
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            for pin in self.pins.values():
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            self._enabled = True
            self._init_error = ""
        except Exception as exc:
            self._enabled = False
            self._init_error = repr(exc)

    def apply(self, leds: Dict[str, bool]) -> None:
        for name in self._last_outputs.keys():
            self._last_outputs[name] = bool(leds.get(name, False))
        if not self._enabled or not self._gpio:
            return
        for name, pin in self.pins.items():
            val = bool(leds.get(name, False))
            self._gpio.output(pin, self._gpio.HIGH if val else self._gpio.LOW)

    def apply_main_lights(self, leds: Dict[str, bool]) -> None:
        self._last_outputs["green"] = bool(leds.get("green", False))
        self._last_outputs["yellow"] = bool(leds.get("yellow", False))
        self._last_outputs["red"] = bool(leds.get("red", False))
        self._last_outputs["buzzer"] = False
        if not self._enabled or not self._gpio:
            return
        for name in ("green", "yellow", "red"):
            pin = self.pins[name]
            val = bool(leds.get(name, False))
            self._gpio.output(pin, self._gpio.HIGH if val else self._gpio.LOW)
        self._gpio.output(self.pins["buzzer"], self._gpio.LOW)

    def start_startup_blink(self) -> None:
        if not self._enabled or not self._gpio:
            return
        gpio = self._gpio
        if gpio is None:
            return
        if self._startup_blink_thread and self._startup_blink_thread.is_alive():
            return

        self._startup_blink_stop.clear()

        def _loop() -> None:
            yellow_pin = self.pins["yellow"]
            green_pin = self.pins["green"]
            red_pin = self.pins["red"]
            buzzer_pin = self.pins["buzzer"]
            on = False
            while not self._startup_blink_stop.is_set():
                on = not on
                self._last_outputs["green"] = on
                self._last_outputs["red"] = False
                self._last_outputs["buzzer"] = False
                self._last_outputs["yellow"] = False

                gpio.output(green_pin, gpio.HIGH if on else gpio.LOW)
                gpio.output(red_pin, gpio.LOW)
                gpio.output(buzzer_pin, gpio.LOW)
                gpio.output(yellow_pin, gpio.LOW)
                time.sleep(0.35)

        self._startup_blink_thread = threading.Thread(target=_loop, daemon=True)
        self._startup_blink_thread.start()

    def stop_startup_blink(self) -> None:
        self._startup_blink_stop.set()
        if self._startup_blink_thread and self._startup_blink_thread.is_alive():
            self._startup_blink_thread.join(timeout=1.0)
        self._startup_blink_thread = None

        self._last_outputs["green"] = False
        self._last_outputs["yellow"] = False
        if self._enabled and self._gpio:
            self._gpio.output(self.pins["green"], self._gpio.LOW)
            self._gpio.output(self.pins["yellow"], self._gpio.LOW)

    def buzz(self, times: int, on_sec: float = 0.12, off_sec: float = 0.08) -> None:
        if not self._enabled or not self._gpio:
            return
        pin = self.pins["buzzer"]
        for _ in range(max(0, times)):
            self._last_outputs["buzzer"] = True
            self._gpio.output(pin, self._gpio.HIGH)
            time.sleep(on_sec)
            self._last_outputs["buzzer"] = False
            self._gpio.output(pin, self._gpio.LOW)
            time.sleep(off_sec)

    def configure_button(self, pin: int, pull: str = "up") -> bool:
        if not self._enabled or not self._gpio:
            return False
        gpio = self._gpio
        if gpio is None:
            return False

        pull_mode = pull if pull in ("up", "down", "off") else "up"
        try:
            if pull_mode == "up":
                pud = gpio.PUD_UP
            elif pull_mode == "down":
                pud = gpio.PUD_DOWN
            else:
                pud = gpio.PUD_OFF
            gpio.setup(pin, gpio.IN, pull_up_down=pud)
            self._button_pin = pin
            self._button_pull = pull_mode
            self._button_error = ""
            return True
        except Exception as exc:
            self._button_error = repr(exc)
            return False

    def is_button_pressed(self) -> bool:
        if not self._enabled or not self._gpio or self._button_pin is None:
            return False
        level = self._gpio.input(self._button_pin)
        if self._button_pull == "up":
            return level == self._gpio.LOW
        return level == self._gpio.HIGH

    def get_status(self) -> Dict[str, object]:
        button_pressed: Optional[bool] = None
        if self._enabled and self._gpio and self._button_pin is not None:
            try:
                button_pressed = self.is_button_pressed()
            except Exception:
                button_pressed = None
        return {
            "available": self._enabled,
            "init_error": self._init_error,
            "pins": dict(self.pins),
            "outputs": dict(self._last_outputs),
            "button_pin": self._button_pin,
            "button_pull": self._button_pull,
            "button_pressed": button_pressed,
            "button_error": self._button_error,
        }


class MailLightMonitor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = GraphClient(settings)
        self.gpio = GpioLightController(buzzer_pin=settings.buzzer_pin)
        self.log = LogBuffer()
        self._lock = threading.Lock()
        self._state = LightState(
            overall="unknown",
            reason="起動直後。まだメール判定していません。",
            updated_at=self._now_iso(),
            mail_subject="",
            mail_received_at="",
            leds={"green": True, "yellow": False, "buzzer": False, "red": False},
            host_states={},
            host_metrics={},
            gpio_status=self.gpio.get_status(),
            startup_blinking=True,
            button_status={
                "enabled": bool(settings.button_enabled),
                "configured": False,
                "pin": settings.button_pin,
                "pull": settings.button_pull,
                "last_pressed_at": "",
                "silenced": False,
            },
        )
        self._host_states: Dict[str, str] = {}
        self._host_metrics: Dict[str, Dict[str, object]] = {}
        self._open_problem_since: Dict[str, datetime] = {}
        self._processed_ids: set[str] = set()
        self._initialized = False
        self._silenced_by_button = False
        self._button_last_pressed_at = ""
        self._button_configured = False
        self._button_thread: Optional[threading.Thread] = None
        self._button_stop = threading.Event()
        self.gpio.start_startup_blink()
        self._start_button_watcher()

    def _button_status_view(self) -> Dict[str, object]:
        is_pressed = False
        if self._button_configured:
            try:
                is_pressed = self.gpio.is_button_pressed()
            except Exception:
                is_pressed = False
        return {
            "enabled": bool(self.settings.button_enabled),
            "configured": self._button_configured,
            "pin": self.settings.button_pin,
            "pull": self.settings.button_pull,
            "last_pressed_at": self._button_last_pressed_at,
            "silenced": self._silenced_by_button,
            "is_pressed": is_pressed,
        }

    @staticmethod
    def _silenced_leds() -> Dict[str, bool]:
        return {
            "green": False,
            "yellow": False,
            "buzzer": False,
            "red": False,
        }

    def _start_button_watcher(self) -> None:
        if not self.settings.button_enabled:
            return
        self._button_configured = self.gpio.configure_button(
            self.settings.button_pin,
            self.settings.button_pull,
        )
        if not self._button_configured:
            return

        interval = max(0.02, float(self.settings.button_poll_interval))
        self._button_stop.clear()

        def _watch_loop() -> None:
            was_pressed = False
            while not self._button_stop.is_set():
                pressed = self.gpio.is_button_pressed()
                if pressed and not was_pressed:
                    self._handle_button_press()
                was_pressed = pressed
                time.sleep(interval)

        self._button_thread = threading.Thread(target=_watch_loop, daemon=True)
        self._button_thread.start()

    def _handle_button_press(self) -> None:
        self._button_last_pressed_at = self._now_iso()
        self._silenced_by_button = True
        self.log.info("ボタン押下: 全LED消灯")
        self.gpio.stop_startup_blink()
        self.gpio.apply_main_lights(self._silenced_leds())
        self.gpio.buzz(1, on_sec=0.5, off_sec=0.0)
        with self._lock:
            self._state.leds = self._silenced_leds()
            self._state.button_status = self._button_status_view()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _strip_html(raw: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _detect_status(subject: str, body: str) -> Optional[str]:
        s = (subject or "").lower()
        b = (body or "").lower()
        resolved_keys = [
            "resolved",
            "problem has been resolved",
            "障害が復旧しました",
            "復旧",
        ]
        problem_keys = [
            "problem:",
            "problem started",
            "障害が発生しました",
        ]
        warning_keys = ["warning", "警告", "アラート", "alert"]

        if any(k in s or k in b for k in resolved_keys):
            return "ok"
        if any(k in s or k in b for k in problem_keys):
            return "problem"
        if any(k in s or k in b for k in warning_keys):
            return "warning"
        return None

    @staticmethod
    def _parse_received_datetime(received: str) -> Optional[datetime]:
        raw = (received or "").strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        seconds = max(0, int(total_seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {sec}s"
        return f"{minutes}m {sec}s"

    def _ensure_host_metric(self, host: str) -> Dict[str, object]:
        metric = self._host_metrics.get(host)
        if metric is None:
            metric = {
                "status": "unknown",
                "host": host,
                "host_ip": "",
                "severity": "",
                "problem_started_at": "",
                "last_resolved_at": "",
                "last_recovery_seconds": None,
                "last_recovery_text": "",
                "ongoing_problem_seconds": None,
                "ongoing_problem_text": "",
                "last_event_subject": "",
                "last_event_received_at": "",
            }
            self._host_metrics[host] = metric
        return metric

    @staticmethod
    def _extract_host_ip(body: str) -> str:
        m = re.search(r"\bHost\s*IP\s*:\s*([^\s<]+)", body, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _extract_severity(body: str) -> str:
        m = re.search(r"\bSeverity\s*:\s*([^\s<]+)", body, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _is_high_or_above(severity: str) -> bool:
        level = (severity or "").strip().lower()
        if not level:
            return False
        return level in ("high", "disaster")

    def _build_host_metrics_view(self) -> Dict[str, Dict[str, object]]:
        view: Dict[str, Dict[str, object]] = {}
        now_dt = self._now_utc()
        for host, metric in self._host_metrics.items():
            copied = dict(metric)
            started = self._open_problem_since.get(host)
            if started and copied.get("status") == "problem":
                seconds = int((now_dt - started).total_seconds())
                if seconds >= 0:
                    copied["ongoing_problem_seconds"] = seconds
                    copied["ongoing_problem_text"] = self._format_duration(seconds)
            view[host] = copied
        return view

    @staticmethod
    def _extract_host(subject: str, body: str) -> str:
        m = re.search(r"【([^】]+)】", subject)
        if m:
            return m.group(1).strip()

        m = re.search(r"\bHost\s*:\s*([^\s<]+)", body, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()

        return "unknown"

    def _aggregate(
        self, host_states: Dict[str, str]
    ) -> Tuple[str, Dict[str, bool], str]:
        for host, status in host_states.items():
            if status == "ok":
                continue
            metric = self._host_metrics.get(host) or {}
            severity = str(metric.get("severity") or "")
            if self._is_high_or_above(severity):
                return (
                    "high",
                    {"green": False, "yellow": False, "buzzer": False, "red": True},
                    "severity が high 以上のホストがあります。",
                )
        return (
            "normal",
            {"green": False, "yellow": False, "buzzer": False, "red": False},
            "問題は起きていません。",
        )

    def _build_snapshot_state(self, messages: List[Dict[str, object]]) -> LightState:
        host_states: Dict[str, str] = {}
        self._host_metrics = {}
        self._open_problem_since = {}
        latest_subject = ""
        latest_received = ""

        for msg in reversed(messages):
            message_id = str(msg.get("id") or "")
            if message_id:
                self._processed_ids.add(message_id)

            subject = str(msg.get("subject") or "")
            body = ""
            body_data = msg.get("body")
            if isinstance(body_data, dict):
                body = str(body_data.get("content") or "")
            body_text = self._strip_html(body)

            status = self._detect_status(subject, body_text)
            if not status:
                continue

            host = self._extract_host(subject, body_text)
            received = str(msg.get("receivedDateTime") or "")
            received_dt = self._parse_received_datetime(received)
            metric = self._ensure_host_metric(host)
            host_ip = self._extract_host_ip(body_text)
            severity = self._extract_severity(body_text)

            host_states[host] = status
            metric["status"] = status
            metric["last_event_subject"] = subject
            metric["last_event_received_at"] = received
            if host_ip:
                metric["host_ip"] = host_ip
            if severity:
                metric["severity"] = severity

            sev_label = f" severity={severity}" if severity else ""
            self.log.info(
                f"[初回] host={host} status={status}{sev_label}"
                f" / {subject}"
            )

            if status == "problem":
                metric["problem_started_at"] = received
                metric["ongoing_problem_seconds"] = None
                metric["ongoing_problem_text"] = ""
                if received_dt:
                    self._open_problem_since[host] = received_dt
            elif status == "ok":
                metric["last_resolved_at"] = received
                metric["ongoing_problem_seconds"] = None
                metric["ongoing_problem_text"] = ""
                started = self._open_problem_since.get(host)
                if started and received_dt:
                    duration = int((received_dt - started).total_seconds())
                    if duration >= 0:
                        metric["last_recovery_seconds"] = duration
                        metric["last_recovery_text"] = self._format_duration(duration)
                self._open_problem_since.pop(host, None)
            elif status == "warning":
                metric["ongoing_problem_seconds"] = None
                metric["ongoing_problem_text"] = ""

            if not latest_subject:
                latest_subject = subject
                latest_received = received

        self._host_states = host_states
        overall, leds, reason = self._aggregate(host_states)
        self.log.info(f"初回判定完了: overall={overall} / {reason}")
        effective_leds = leds
        if self._silenced_by_button:
            effective_leds = self._silenced_leds()
            reason = f"{reason}（ボタンで消灯中）"

        return LightState(
            overall=overall,
            reason=reason,
            updated_at=self._now_iso(),
            mail_subject=latest_subject,
            mail_received_at=latest_received,
            leds=effective_leds,
            host_states=dict(host_states),
            host_metrics=self._build_host_metrics_view(),
            gpio_status=self.gpio.get_status(),
            startup_blinking=False,
            button_status=self._button_status_view(),
        )

    def _process_incremental(self, messages: List[Dict[str, object]]) -> LightState:
        events: List[Tuple[str, str, str, str]] = []
        for msg in reversed(messages):
            message_id = str(msg.get("id") or "")
            if not message_id or message_id in self._processed_ids:
                continue
            self._processed_ids.add(message_id)

            subject = str(msg.get("subject") or "")
            body = ""
            body_data = msg.get("body")
            if isinstance(body_data, dict):
                body = str(body_data.get("content") or "")
            body_text = self._strip_html(body)
            status = self._detect_status(subject, body_text)
            if not status:
                continue

            host = self._extract_host(subject, body_text)
            metric = self._ensure_host_metric(host)
            self._host_states[host] = status
            received = str(msg.get("receivedDateTime") or "")
            received_dt = self._parse_received_datetime(received)
            host_ip = self._extract_host_ip(body_text)
            severity = self._extract_severity(body_text)

            metric["status"] = status
            metric["last_event_subject"] = subject
            metric["last_event_received_at"] = received
            if host_ip:
                metric["host_ip"] = host_ip
            if severity:
                metric["severity"] = severity

            sev_label = f" severity={severity}" if severity else ""
            self.log.info(
                f"新規メール: host={host} status={status}{sev_label}"
                f" / {subject}"
            )

            if status == "problem":
                metric["problem_started_at"] = received
                metric["ongoing_problem_seconds"] = None
                metric["ongoing_problem_text"] = ""
                if received_dt:
                    self._open_problem_since[host] = received_dt
            elif status == "ok":
                metric["last_resolved_at"] = received
                metric["ongoing_problem_seconds"] = None
                metric["ongoing_problem_text"] = ""
                started = self._open_problem_since.get(host)
                if started and received_dt:
                    duration = int((received_dt - started).total_seconds())
                    if duration >= 0:
                        metric["last_recovery_seconds"] = duration
                        metric["last_recovery_text"] = self._format_duration(duration)
                self._open_problem_since.pop(host, None)
            elif status == "warning":
                metric["ongoing_problem_seconds"] = None
                metric["ongoing_problem_text"] = ""

            events.append((host, status, subject, received))

        overall, leds, default_reason = self._aggregate(self._host_states)

        if events:
            host, status, subject, received = events[-1]
            self._silenced_by_button = False
            self.gpio.apply_main_lights(leds)
            if overall == "high":
                self.gpio.buzz(2, off_sec=0.2)
            reason = f"{host} が {status} に更新されました。"
            self.log.info(f"判定更新: overall={overall} / {reason}")
            return LightState(
                overall=overall,
                reason=reason,
                updated_at=self._now_iso(),
                mail_subject=subject,
                mail_received_at=received,
                leds=leds,
                host_states=dict(self._host_states),
                host_metrics=self._build_host_metrics_view(),
                gpio_status=self.gpio.get_status(),
                startup_blinking=False,
                button_status=self._button_status_view(),
            )

        effective_leds = leds
        reason = default_reason
        if self._silenced_by_button:
            effective_leds = self._silenced_leds()
            reason = f"{default_reason}（ボタンで消灯中）"
        self.gpio.apply_main_lights(effective_leds)
        return LightState(
            overall=overall,
            reason=reason,
            updated_at=self._now_iso(),
            mail_subject=self._state.mail_subject,
            mail_received_at=self._state.mail_received_at,
            leds=effective_leds,
            host_states=dict(self._host_states),
            host_metrics=self._build_host_metrics_view(),
            gpio_status=self.gpio.get_status(),
            startup_blinking=False,
            button_status=self._button_status_view(),
        )

    def get_logs(self) -> List[Dict[str, str]]:
        return self.log.get()

    def refresh_once(self) -> Dict[str, object]:
        top_n = max(self.settings.test_top, self.settings.pi_top)
        self.log.info(f"メール取得: 最大{top_n}件")
        messages = self.client.get_messages(
            top=top_n,
            folder=self.settings.mail_folder,
            recipient=self.settings.target_recipient,
            unread_only=False,
        )
        self.log.info(f"メール取得完了: {len(messages)}件")
        if not self._initialized:
            new_state = self._build_snapshot_state(messages)
            self.gpio.stop_startup_blink()
            self.gpio.apply_main_lights(new_state.leds)
            self._initialized = True
        else:
            new_state = self._process_incremental(messages)
        with self._lock:
            self._state = new_state
            return self._state.to_dict()

    def get_state(self) -> Dict[str, object]:
        with self._lock:
            self._state.gpio_status = self.gpio.get_status()
            self._state.button_status = self._button_status_view()
            return self._state.to_dict()

    def run_forever(self, interval_sec: int) -> None:
        while True:
            try:
                self.refresh_once()
            except Exception as exc:
                self.log.error(f"メール取得/判定でエラー: {exc}")
                with self._lock:
                    self._state = LightState(
                        overall="error",
                        reason=f"メール取得/判定でエラー: {exc}",
                        updated_at=self._now_iso(),
                        mail_subject="",
                        mail_received_at="",
                        leds={
                            "green": False,
                            "yellow": False,
                            "buzzer": False,
                            "red": False,
                        },
                        host_states=dict(self._host_states),
                        host_metrics=self._build_host_metrics_view(),
                        gpio_status=self.gpio.get_status(),
                        startup_blinking=False,
                        button_status=self._button_status_view(),
                    )
            time.sleep(max(1.0, float(interval_sec)))
