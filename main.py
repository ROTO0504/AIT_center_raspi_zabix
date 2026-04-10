import sys
import time
from typing import Dict

from monitor_service import MailLightMonitor
from settings import Settings
from utils import is_raspberry_pi


def _print_state(state: Dict[str, object]) -> None:
    print("=== Light Monitor State ===")
    print("Overall:", state.get("overall", "unknown"))
    print("Reason:", state.get("reason", "-"))
    print("Updated:", state.get("updated_at", "-"))
    print("Subject:", state.get("mail_subject", "-"))
    print("Received:", state.get("mail_received_at", "-"))

    print("\n-- Lights --")
    leds = state.get("leds") or {}
    if isinstance(leds, dict):
        print("GREEN:", "ON" if leds.get("green") else "OFF")
        print("YELLOW:", "ON" if leds.get("yellow") else "OFF")
        print("BUZZER:", "ON" if leds.get("buzzer") else "OFF")
        print("RED:", "ON" if leds.get("red") else "OFF")

    print("\n-- Hosts --")
    host_states = state.get("host_states") or {}
    host_metrics = state.get("host_metrics") or {}
    if isinstance(host_states, dict) and host_states:
        for host, host_state in host_states.items():
            suffix = ""
            if isinstance(host_metrics, dict):
                metric = host_metrics.get(host) or {}
                if isinstance(metric, dict):
                    recovery = metric.get("last_recovery_text")
                    if recovery:
                        suffix = f" / recovery={recovery}"
                    elif host_state == "problem":
                        suffix = " / recovery=pending"
            print(f"{host}: {host_state}{suffix}")
    else:
        print("(none)")

    print("\n-- GPIO --")
    gpio_status = state.get("gpio_status") or {}
    if isinstance(gpio_status, dict):
        available = gpio_status.get("available", False)
        print("Available:", "yes" if available else "no")
        pins = gpio_status.get("pins") or {}
        outputs = gpio_status.get("outputs") or {}
        if isinstance(pins, dict) and isinstance(outputs, dict):
            for key in ("green", "yellow", "buzzer", "red"):
                pin = pins.get(key, "-")
                out = "ON" if outputs.get(key) else "OFF"
                print(f"{key.upper()} (GPIO {pin}): {out}")

    print("\n-- Button --")
    button_status = state.get("button_status") or {}
    if isinstance(button_status, dict):
        print("Enabled:", "yes" if button_status.get("enabled") else "no")
        print("Configured:", "yes" if button_status.get("configured") else "no")
        print("Pin:", button_status.get("pin", "-"))
        print("Pull:", button_status.get("pull", "-"))
        print("Silenced:", "yes" if button_status.get("silenced") else "no")
        print("Last pressed:", button_status.get("last_pressed_at") or "-")
    print()


def main() -> int:
    try:
        settings = Settings.from_env()
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    monitor = MailLightMonitor(settings)

    if settings.target_recipient:
        print(f"Recipient filter: {settings.target_recipient}")
    else:
        print("Recipient filter: none")

    if settings.run_mode == "auto":
        on_pi = is_raspberry_pi()
    else:
        on_pi = settings.run_mode == "raspi"

    def fetch_once() -> int:
        try:
            state = monitor.refresh_once()
        except Exception as exc:
            print(f"Fetch error: {exc}", file=sys.stderr)
            return 1

        _print_state(state)
        return 0

    if on_pi:
        print(
            "Raspberry Pi mode. "
            f"Polling every {settings.mail_poll_interval} seconds..."
        )
        try:
            while True:
                fetch_once()
                time.sleep(max(1.0, settings.mail_poll_interval))
        except KeyboardInterrupt:
            print("Stopped.")
            return 0

    print("Test mode. Running once.")
    return fetch_once()


if __name__ == "__main__":
    sys.exit(main())
