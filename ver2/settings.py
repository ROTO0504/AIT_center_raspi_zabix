import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from env_loader import load_env


def _parse_scopes(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    tokens = [tok.strip() for tok in raw.replace(",", " ").split() if tok.strip()]
    return tokens or None


def _parse_bool(raw: Optional[str], default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Settings:
    client_id: str
    tenant_id: str
    client_secret: Optional[str]
    mailbox_user: str
    mail_folder: str
    target_recipient: Optional[str]
    unread_only: bool
    run_mode: str
    poll_interval: int
    mail_poll_interval: float
    test_top: int
    pi_top: int
    open_browser: bool
    scopes: Optional[List[str]]
    button_enabled: bool
    button_pin: int
    button_pull: str
    button_poll_interval: float

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "Settings":
        env_path = env_path or Path(__file__).with_name(".env")
        load_env(env_path)

        client_id = os.getenv("APP_ID") or os.getenv("CLIENT_ID")
        tenant_id = os.getenv("TENANT_ID")
        if not client_id or not tenant_id:
            raise ValueError("APP_ID and TENANT_ID must be set")

        client_secret = os.getenv("CLIENT_SECRET")
        mailbox_user = (os.getenv("MAILBOX_USER") or "me").strip() or "me"
        mail_folder = (os.getenv("MAIL_FOLDER") or "Inbox").strip() or "Inbox"
        target_recipient = (os.getenv("TARGET_RECIPIENT") or "").strip() or None
        if target_recipient and target_recipient.lower() in ("*", "any", "all"):
            target_recipient = None

        unread_only = _parse_bool(os.getenv("UNREAD_ONLY"), default=True)
        run_mode = (os.getenv("RUN_MODE") or "auto").strip().lower()
        if run_mode not in ("auto", "mac", "raspi"):
            run_mode = "auto"

        poll_interval = int(os.getenv("POLL_INTERVAL") or 30)
        mail_poll_interval = float(
            os.getenv("MAIL_POLL_INTERVAL") or os.getenv("POLL_INTERVAL") or 5
        )
        test_top = int(os.getenv("TEST_TOP") or 100)
        pi_top = int(os.getenv("PI_TOP") or 10)
        open_browser = _parse_bool(os.getenv("OPEN_BROWSER"), default=True)
        scopes = _parse_scopes(os.getenv("GRAPH_SCOPES"))
        button_enabled = _parse_bool(os.getenv("BUTTON_ENABLED"), default=True)
        button_pin = int(os.getenv("BUTTON_PIN") or 12)
        button_pull = (os.getenv("BUTTON_PULL") or "up").strip().lower()
        if button_pull not in ("up", "down", "off"):
            button_pull = "up"
        button_poll_interval = float(os.getenv("BUTTON_POLL_INTERVAL") or 0.1)

        return cls(
            client_id=client_id,
            tenant_id=tenant_id,
            client_secret=client_secret,
            mailbox_user=mailbox_user,
            mail_folder=mail_folder,
            target_recipient=target_recipient,
            unread_only=unread_only,
            run_mode=run_mode,
            poll_interval=poll_interval,
            mail_poll_interval=mail_poll_interval,
            test_top=test_top,
            pi_top=pi_top,
            open_browser=open_browser,
            scopes=scopes,
            button_enabled=button_enabled,
            button_pin=button_pin,
            button_pull=button_pull,
            button_poll_interval=button_poll_interval,
        )
