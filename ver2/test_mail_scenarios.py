from __future__ import annotations

import argparse
import copy
import importlib
import json
import sys
import types
from dataclasses import dataclass, field
from typing import Any, Dict, List

from settings import Settings

Message = Dict[str, Any]


@dataclass(frozen=True)
class Scenario:
    name: str
    summary: str
    expectation: str
    batches: List[List[Message]]
    button_press_after_steps: List[int] = field(default_factory=list)


def _message(
    *,
    message_id: str,
    subject: str,
    received: str,
    body_lines: List[str],
) -> Message:
    return {
        "id": message_id,
        "subject": subject,
        "receivedDateTime": received,
        "body": {"content": "<br>".join(body_lines)},
    }


def _problem_message(
    *,
    message_id: str,
    host: str,
    severity: str,
    received: str,
    subject_prefix: str = "Problem started",
) -> Message:
    return _message(
        message_id=message_id,
        subject=f"{subject_prefix}: 【{host}】",
        received=received,
        body_lines=[
            "障害が発生しました",
            f"Host : {host}",
            f"Host IP : 192.168.1.{10 + len(host)}",
            f"Severity : {severity}",
        ],
    )


def _warning_message(
    *,
    message_id: str,
    host: str,
    received: str,
    severity: str = "warning",
) -> Message:
    return _message(
        message_id=message_id,
        subject=f"Warning: 【{host}】",
        received=received,
        body_lines=[
            "警告を検知しました",
            f"Host : {host}",
            f"Host IP : 192.168.1.{20 + len(host)}",
            f"Severity : {severity}",
        ],
    )


def _resolved_message(
    *,
    message_id: str,
    host: str,
    received: str,
    severity: str = "high",
) -> Message:
    return _message(
        message_id=message_id,
        subject=f"Problem has been resolved: 【{host}】",
        received=received,
        body_lines=[
            "障害が復旧しました",
            f"Host : {host}",
            f"Host IP : 192.168.1.{30 + len(host)}",
            f"Severity : {severity}",
        ],
    )


def _ignored_message(*, message_id: str, received: str) -> Message:
    return _message(
        message_id=message_id,
        subject="FYI: backup completed",
        received=received,
        body_lines=[
            "This mail should be ignored by the monitor.",
            "Host : backup01",
            "Severity : information",
        ],
    )


SCENARIOS: Dict[str, Scenario] = {
    "startup_empty": Scenario(
        name="startup_empty",
        summary="メール0件で初回判定を確認",
        expectation="overall=normal、赤LED OFF、ブザーなし",
        batches=[[]],
    ),
    "high_problem": Scenario(
        name="high_problem",
        summary="high 障害メールを新着で受信",
        expectation="overall=high、赤LED ON、ブザー2回",
        batches=[
            [],
            [
                _problem_message(
                    message_id="msg-high-1",
                    host="db01",
                    severity="high",
                    received="2026-03-06T00:00:10Z",
                )
            ],
        ],
    ),
    "disaster_problem": Scenario(
        name="disaster_problem",
        summary="disaster 障害メールを新着で受信",
        expectation="overall=high、赤LED ON、ブザー2回",
        batches=[
            [],
            [
                _problem_message(
                    message_id="msg-disaster-1",
                    host="app01",
                    severity="disaster",
                    received="2026-03-06T00:01:00Z",
                )
            ],
        ],
    ),
    "warning_only": Scenario(
        name="warning_only",
        summary="warning メールのみ受信",
        expectation="overall=normal、赤LED OFF、ブザーなし",
        batches=[
            [],
            [
                _warning_message(
                    message_id="msg-warning-1",
                    host="web01",
                    received="2026-03-06T00:02:00Z",
                )
            ],
        ],
    ),
    "resolved_after_problem": Scenario(
        name="resolved_after_problem",
        summary="high 障害のあと復旧メールを受信",
        expectation="最終的に overall=normal、赤LED OFF、復旧時間あり",
        batches=[
            [],
            [
                _problem_message(
                    message_id="msg-problem-2",
                    host="db02",
                    severity="high",
                    received="2026-03-06T00:03:00Z",
                )
            ],
            [
                _resolved_message(
                    message_id="msg-resolved-2",
                    host="db02",
                    received="2026-03-06T00:08:30Z",
                ),
                _problem_message(
                    message_id="msg-problem-2",
                    host="db02",
                    severity="high",
                    received="2026-03-06T00:03:00Z",
                ),
            ],
        ],
    ),
    "mixed_hosts": Scenario(
        name="mixed_hosts",
        summary="warning ホストと high ホストが混在",
        expectation="high が1台でもあれば overall=high、赤LED ON",
        batches=[
            [],
            [
                _warning_message(
                    message_id="msg-warning-3",
                    host="web02",
                    received="2026-03-06T00:04:00Z",
                )
            ],
            [
                _problem_message(
                    message_id="msg-high-3",
                    host="db03",
                    severity="high",
                    received="2026-03-06T00:04:30Z",
                ),
                _warning_message(
                    message_id="msg-warning-3",
                    host="web02",
                    received="2026-03-06T00:04:00Z",
                ),
            ],
        ],
    ),
    "ignored_mail": Scenario(
        name="ignored_mail",
        summary="判定対象外メールを受信",
        expectation="overall=normal のまま、状態変化なし",
        batches=[
            [],
            [
                _ignored_message(
                    message_id="msg-ignore-1",
                    received="2026-03-06T00:05:00Z",
                )
            ],
        ],
    ),
    "high_then_button": Scenario(
        name="high_then_button",
        summary="high 障害メール受信後にボタンを押して消灯",
        expectation=(
            "overall=high のまま、赤LED OFF、消灯中、" "ボタン押下でブザー1回追加"
        ),
        batches=[
            [],
            [
                _problem_message(
                    message_id="msg-high-button-1",
                    host="db04",
                    severity="high",
                    received="2026-03-06T00:06:00Z",
                )
            ],
            [
                _problem_message(
                    message_id="msg-high-button-1",
                    host="db04",
                    severity="high",
                    received="2026-03-06T00:06:00Z",
                )
            ],
        ],
        button_press_after_steps=[2],
    ),
}


class _ScenarioGraphClient:
    def __init__(
        self,
        _settings: Settings,
        batches: List[List[Message]],
    ) -> None:
        self._batches = copy.deepcopy(batches)
        self._calls = 0

    def get_messages(
        self,
        top: int,
        folder: str,
        recipient: str | None,
        unread_only: bool,
    ) -> List[Message]:
        _ = (top, folder, recipient, unread_only)
        if not self._batches:
            return []
        index = min(self._calls, len(self._batches) - 1)
        self._calls += 1
        return copy.deepcopy(self._batches[index])


def _build_settings() -> Settings:
    return Settings(
        client_id="dummy-client-id",
        tenant_id="dummy-tenant-id",
        client_secret=None,
        mailbox_user="me",
        mail_folder="Inbox",
        target_recipient=None,
        unread_only=False,
        run_mode="raspi",
        poll_interval=30,
        mail_poll_interval=1.0,
        test_top=100,
        pi_top=10,
        open_browser=False,
        scopes=None,
        buzzer_pin=5,
        button_enabled=False,
        button_pin=21,
        button_pull="up",
        button_poll_interval=0.1,
    )


def _load_monitor_module() -> Any:
    if "monitor_service" in sys.modules:
        return sys.modules["monitor_service"]

    original_graph_client = sys.modules.get("graph_client")
    fake_graph_client = types.ModuleType("graph_client")

    class PlaceholderGraphClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "test_mail_scenarios.py では実際の GraphClient は使用しません。"
            )

    setattr(fake_graph_client, "GraphClient", PlaceholderGraphClient)
    sys.modules["graph_client"] = fake_graph_client
    try:
        return importlib.import_module("monitor_service")
    finally:
        if original_graph_client is not None:
            sys.modules["graph_client"] = original_graph_client
        else:
            sys.modules.pop("graph_client", None)


def run_scenario(scenario: Scenario) -> Dict[str, Any]:
    monitor_module = _load_monitor_module()
    original_graph_client = monitor_module.GraphClient

    class ScenarioGraphClient(_ScenarioGraphClient):
        def __init__(self, settings: Settings) -> None:
            super().__init__(settings, scenario.batches)

    monitor_module.GraphClient = ScenarioGraphClient
    try:
        monitor = monitor_module.MailLightMonitor(_build_settings())
    finally:
        monitor_module.GraphClient = original_graph_client

    buzz_events: List[Dict[str, Any]] = []
    original_buzz = monitor.gpio.buzz

    def traced_buzz(
        times: int,
        on_sec: float = 0.12,
        off_sec: float = 0.08,
    ) -> None:
        buzz_events.append({"times": times, "on_sec": on_sec, "off_sec": off_sec})
        original_buzz(times, on_sec=on_sec, off_sec=off_sec)

    monitor.gpio.buzz = traced_buzz  # type: ignore[assignment]

    steps: List[Dict[str, Any]] = []
    for index in range(len(scenario.batches)):
        state = monitor.refresh_once()
        steps.append(
            {
                "label": f"step {index + 1}",
                "step": index + 1,
                "overall": state.get("overall"),
                "reason": state.get("reason"),
                "mail_subject": state.get("mail_subject"),
                "mail_received_at": state.get("mail_received_at"),
                "leds": state.get("leds"),
                "host_states": state.get("host_states"),
                "button_silenced": ((state.get("button_status") or {}).get("silenced")),
            }
        )

        if (index + 1) in scenario.button_press_after_steps:
            monitor._handle_button_press()
            pressed_state = monitor.get_state()
            steps.append(
                {
                    "label": f"step {index + 1} / button press",
                    "step": index + 1,
                    "overall": pressed_state.get("overall"),
                    "reason": pressed_state.get("reason"),
                    "mail_subject": pressed_state.get("mail_subject"),
                    "mail_received_at": pressed_state.get("mail_received_at"),
                    "leds": pressed_state.get("leds"),
                    "host_states": pressed_state.get("host_states"),
                    "button_silenced": (
                        (pressed_state.get("button_status") or {}).get("silenced")
                    ),
                }
            )

    final_state = monitor.get_state()
    return {
        "scenario": scenario.name,
        "summary": scenario.summary,
        "expectation": scenario.expectation,
        "steps": steps,
        "buzz_events": buzz_events,
        "final_state": final_state,
    }


def _print_text(result: Dict[str, Any]) -> None:
    print(f"Scenario     : {result['scenario']}")
    print(f"Summary      : {result['summary']}")
    print(f"Expectation  : {result['expectation']}")
    print()

    for step in result["steps"]:
        step_label = step.get("label") or f"step {step['step']}"
        print(f"[{step_label}]")
        print(f"  overall  : {step['overall']}")
        print(f"  reason   : {step['reason']}")
        print(f"  subject  : {step['mail_subject'] or '-'}")
        print(f"  received : {step['mail_received_at'] or '-'}")
        print(f"  leds     : {json.dumps(step['leds'], ensure_ascii=False)}")
        hosts_json = json.dumps(step["host_states"], ensure_ascii=False)
        print(f"  hosts    : {hosts_json}")
        print(f"  silenced : {step.get('button_silenced')}")
        print()

    final_state = result["final_state"]
    gpio_status = final_state.get("gpio_status") or {}
    print("[final]")
    print(f"  overall        : {final_state.get('overall')}")
    print(f"  reason         : {final_state.get('reason')}")
    gpio_available = "yes" if gpio_status.get("available") else "no"
    print(f"  gpio_available : {gpio_available}")
    outputs_json = json.dumps(
        gpio_status.get("outputs", {}),
        ensure_ascii=False,
    )
    print(f"  gpio_outputs   : {outputs_json}")
    button_status = final_state.get("button_status") or {}
    print(f"  silenced       : {button_status.get('silenced')}")
    if result["buzz_events"]:
        buzz_json = json.dumps(result["buzz_events"], ensure_ascii=False)
        print(f"  buzz_calls     : {buzz_json}")
    else:
        print("  buzz_calls     : []")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zabbix メール判定のテストシナリオをローカルで再生します。"
    )
    parser.add_argument("scenario", nargs="?", help="実行するシナリオ名")
    parser.add_argument(
        "--list",
        action="store_true",
        help="利用可能なシナリオ一覧を表示",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="結果を JSON で出力",
    )
    args = parser.parse_args()

    if args.list or not args.scenario:
        print("Available scenarios:")
        for scenario in SCENARIOS.values():
            print(f"- {scenario.name}: {scenario.summary}")
        return 0

    scenario = SCENARIOS.get(args.scenario)
    if scenario is None:
        print(f"Unknown scenario: {args.scenario}")
        print("Use --list to show scenarios.")
        return 1

    result = run_scenario(scenario)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
