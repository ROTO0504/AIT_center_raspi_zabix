from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

try:
    from env_loader import load_env
except Exception:

    def load_env(env_path: Path) -> None:
        if not env_path.exists():
            return
        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


DEFAULT_RED_PIN = 26
DEFAULT_YELLOW_PIN = 13
DEFAULT_BUZZER_PIN = 19
DEFAULT_BUTTON_PIN = 12
DEFAULT_BUTTON_PULL = "up"


def _load_defaults() -> tuple[int, int, int, int, str]:
    for env_path in (
        Path(__file__).with_name(".env"),
        Path(__file__).resolve().parent.parent / "ver2" / ".env",
        Path.cwd() / ".env",
    ):
        load_env(env_path)
    red_pin = int(os.getenv("RED_PIN") or DEFAULT_RED_PIN)
    yellow_pin = int(os.getenv("YELLOW_PIN") or DEFAULT_YELLOW_PIN)
    buzzer_pin = int(os.getenv("BUZZER_PIN") or DEFAULT_BUZZER_PIN)
    button_pin = int(os.getenv("BUTTON_PIN") or DEFAULT_BUTTON_PIN)
    button_pull = (os.getenv("BUTTON_PULL") or DEFAULT_BUTTON_PULL).strip().lower()
    if button_pull not in ("up", "down", "off"):
        button_pull = DEFAULT_BUTTON_PULL
    return red_pin, yellow_pin, buzzer_pin, button_pin, button_pull


class GpioTester:
    def __init__(
        self,
        *,
        red_pin: int,
        yellow_pin: int,
        buzzer_pin: int,
        button_pin: int,
        button_pull: str,
    ) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "RPi.GPIO を読み込めません。Raspberry Pi 上で実行してください。"
            ) from exc

        self.GPIO = GPIO
        self.red_pin = red_pin
        self.yellow_pin = yellow_pin
        self.buzzer_pin = buzzer_pin
        self.button_pin = button_pin
        self.button_pull = button_pull

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.red_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.yellow_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.buzzer_pin, GPIO.OUT, initial=GPIO.LOW)

        if self.button_pull == "up":
            pud = GPIO.PUD_UP
        elif self.button_pull == "down":
            pud = GPIO.PUD_DOWN
        else:
            pud = GPIO.PUD_OFF
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=pud)

    def _button_pud(self) -> int:
        if self.button_pull == "up":
            return self.GPIO.PUD_UP
        if self.button_pull == "down":
            return self.GPIO.PUD_DOWN
        return self.GPIO.PUD_OFF

    def cleanup(self) -> None:
        self.all_off()
        self.GPIO.cleanup()

    def all_off(self) -> None:
        self.GPIO.output(self.red_pin, self.GPIO.LOW)
        self.GPIO.output(self.yellow_pin, self.GPIO.LOW)
        self.GPIO.output(self.buzzer_pin, self.GPIO.LOW)

    def red(self, on: bool) -> None:
        self.GPIO.output(self.red_pin, self.GPIO.HIGH if on else self.GPIO.LOW)

    def yellow(self, on: bool) -> None:
        self.GPIO.output(
            self.yellow_pin,
            self.GPIO.HIGH if on else self.GPIO.LOW,
        )

    def buzz(self, on_sec: float = 0.2) -> None:
        self.GPIO.output(self.buzzer_pin, self.GPIO.HIGH)
        time.sleep(max(0.0, on_sec))
        self.GPIO.output(self.buzzer_pin, self.GPIO.LOW)

    def output_pin(self, pin: int, on: bool) -> None:
        self.GPIO.setup(pin, self.GPIO.OUT, initial=self.GPIO.LOW)
        self.GPIO.output(pin, self.GPIO.HIGH if on else self.GPIO.LOW)

    def blink_pin(
        self,
        pin: int,
        count: int = 5,
        on_sec: float = 0.35,
    ) -> None:
        self.GPIO.setup(pin, self.GPIO.OUT, initial=self.GPIO.LOW)
        for _ in range(max(1, count)):
            self.GPIO.output(pin, self.GPIO.HIGH)
            time.sleep(max(0.01, on_sec))
            self.GPIO.output(pin, self.GPIO.LOW)
            time.sleep(max(0.01, on_sec))

    def watch_input_pin(
        self,
        pin: int,
        seconds: float = 10.0,
        interval: float = 0.1,
        pull: str | None = None,
    ) -> None:
        resolved_pull = (pull or self.button_pull or "up").strip().lower()
        if resolved_pull not in ("up", "down", "off"):
            resolved_pull = "up"
        if resolved_pull == "up":
            pud = self.GPIO.PUD_UP
        elif resolved_pull == "down":
            pud = self.GPIO.PUD_DOWN
        else:
            pud = self.GPIO.PUD_OFF
        self.GPIO.setup(pin, self.GPIO.IN, pull_up_down=pud)
        print(
            "GPIO入力監視開始: " f"{seconds:.1f} 秒 / BCM {pin} / pull={resolved_pull}"
        )
        end_at = time.time() + max(0.1, seconds)
        last_level = None
        while time.time() < end_at:
            level = self.GPIO.input(pin)
            if level != last_level:
                print(f"LEVEL {'HIGH' if level else 'LOW'}")
                last_level = level
            time.sleep(max(0.02, interval))

    def blink(self, name: str, count: int = 5, on_sec: float = 0.35) -> None:
        target = self.red if name == "red" else self.yellow
        for _ in range(max(1, count)):
            target(True)
            time.sleep(max(0.01, on_sec))
            target(False)
            time.sleep(max(0.01, on_sec))

    def button_pressed(self) -> bool:
        level = self.GPIO.input(self.button_pin)
        if self.button_pull == "up":
            return level == self.GPIO.LOW
        return level == self.GPIO.HIGH

    def print_pin_summary(self) -> None:
        print("GPIO pins (BCM):")
        print(f"  RED    : {self.red_pin}")
        print(f"  YELLOW : {self.yellow_pin}")
        print(f"  BUZZER : {self.buzzer_pin}")
        print(f"  BUTTON : {self.button_pin} (pull={self.button_pull})")

    def test_all(self) -> None:
        self.print_pin_summary()
        print("\n[1/4] 赤 LED を 3 回点滅")
        self.blink("red", count=3, on_sec=0.25)
        print("[2/4] 黄 LED を 3 回点滅")
        self.blink("yellow", count=3, on_sec=0.25)
        print("[3/4] ブザーを 2 回鳴動")
        self.buzz(0.15)
        time.sleep(0.2)
        self.buzz(0.15)
        print("[4/4] ボタン監視 10 秒")
        self.watch_button(seconds=10.0)

    def watch_button(
        self,
        seconds: float = 10.0,
        interval: float = 0.1,
    ) -> None:
        print(
            "ボタン監視開始: "
            f"{seconds:.1f} 秒 / BCM {self.button_pin} "
            f"/ pull={self.button_pull}"
        )
        end_at = time.time() + max(0.1, seconds)
        last_state = None
        while time.time() < end_at:
            pressed = self.button_pressed()
            if pressed != last_state:
                print("PRESSED" if pressed else "RELEASED")
                last_state = pressed
            time.sleep(max(0.02, interval))


def build_parser() -> argparse.ArgumentParser:
    red_pin, yellow_pin, buzzer_pin, button_pin, button_pull = _load_defaults()
    parser = argparse.ArgumentParser(description="GPIO 単体テスト用スクリプト")
    parser.add_argument(
        "action",
        choices=(
            "pins",
            "test-all",
            "gpio-on",
            "gpio-off",
            "gpio-blink",
            "gpio-watch",
            "red-on",
            "red-off",
            "yellow-on",
            "yellow-off",
            "red-blink",
            "yellow-blink",
            "buzz",
            "all-off",
            "button-watch",
        ),
        help="実行するテスト内容",
    )
    parser.add_argument("--red-pin", type=int, default=red_pin)
    parser.add_argument("--yellow-pin", type=int, default=yellow_pin)
    parser.add_argument("--buzzer-pin", type=int, default=buzzer_pin)
    parser.add_argument("--button-pin", type=int, default=button_pin)
    parser.add_argument("--button-pull", default=button_pull)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--gpio", type=int, help="任意に指定する BCM GPIO 番号")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.action == "pins":
        print("GPIO pins (BCM):")
        print(f"  RED    : {args.red_pin}")
        print(f"  YELLOW : {args.yellow_pin}")
        print(f"  BUZZER : {args.buzzer_pin}")
        print(f"  BUTTON : {args.button_pin} (pull={args.button_pull})")
        return 0

    try:
        tester = GpioTester(
            red_pin=args.red_pin,
            yellow_pin=args.yellow_pin,
            buzzer_pin=args.buzzer_pin,
            button_pin=args.button_pin,
            button_pull=args.button_pull,
        )
    except Exception as exc:
        print(f"GPIO 初期化エラー: {exc}", file=sys.stderr)
        return 1

    try:
        tester.print_pin_summary()
        print()

        if args.action == "test-all":
            tester.test_all()
        elif args.action == "gpio-on":
            if args.gpio is None:
                parser.error("gpio-on では --gpio が必要です")
            tester.output_pin(args.gpio, True)
            print(f"GPIO {args.gpio} ON")
        elif args.action == "gpio-off":
            if args.gpio is None:
                parser.error("gpio-off では --gpio が必要です")
            tester.output_pin(args.gpio, False)
            print(f"GPIO {args.gpio} OFF")
        elif args.action == "gpio-blink":
            if args.gpio is None:
                parser.error("gpio-blink では --gpio が必要です")
            tester.blink_pin(args.gpio, count=args.count)
        elif args.action == "gpio-watch":
            if args.gpio is None:
                parser.error("gpio-watch では --gpio が必要です")
            tester.watch_input_pin(
                args.gpio,
                seconds=args.seconds,
                interval=args.interval,
                pull=args.button_pull,
            )
        elif args.action == "red-on":
            tester.red(True)
            print("赤 LED ON")
        elif args.action == "red-off":
            tester.red(False)
            print("赤 LED OFF")
        elif args.action == "yellow-on":
            tester.yellow(True)
            print("黄 LED ON")
        elif args.action == "yellow-off":
            tester.yellow(False)
            print("黄 LED OFF")
        elif args.action == "red-blink":
            tester.blink("red", count=args.count)
        elif args.action == "yellow-blink":
            tester.blink("yellow", count=args.count)
        elif args.action == "buzz":
            tester.buzz(args.seconds)
        elif args.action == "all-off":
            tester.all_off()
            print("赤/黄/ブザーを OFF")
        elif args.action == "button-watch":
            tester.watch_button(seconds=args.seconds, interval=args.interval)
    except KeyboardInterrupt:
        print("\n中断しました。")
    finally:
        if args.action not in ("red-on", "yellow-on", "gpio-on"):
            tester.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
