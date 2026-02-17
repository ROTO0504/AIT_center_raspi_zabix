import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import msal
import requests

from settings import Settings
from utils import is_macos

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    def __init__(self, settings: Settings, cache_path: Optional[Path] = None) -> None:
        self.settings = settings
        self.cache_path = cache_path or Path(__file__).with_name("msal_token_cache.bin")
        self.token_cache = msal.SerializableTokenCache()
        if self.cache_path.exists():
            try:
                self.token_cache.deserialize(self.cache_path.read_text())
            except Exception:
                pass

        self.use_confidential = bool(self.settings.client_secret)
        if self.use_confidential:
            self.confidential_app = msal.ConfidentialClientApplication(
                client_id=self.settings.client_id,
                authority=self._authority(),
                client_credential=self.settings.client_secret,
                token_cache=self.token_cache,
            )
            self.public_app = None
        else:
            self.public_app = msal.PublicClientApplication(
                client_id=self.settings.client_id,
                authority=self._authority(),
                token_cache=self.token_cache,
            )
            self.confidential_app = None

    def _authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.settings.tenant_id}"

    def _scopes(self) -> List[str]:
        if self.settings.scopes:
            return self.settings.scopes
        if self.use_confidential:
            return ["https://graph.microsoft.com/.default"]
        return ["Mail.Read"]

    def _save_cache(self) -> None:
        if self.token_cache.has_state_changed:
            try:
                self.cache_path.write_text(self.token_cache.serialize())
            except Exception:
                pass

    def acquire_token(self) -> Dict[str, str]:
        if self.use_confidential:
            if not self.confidential_app:
                raise RuntimeError("Confidential client not initialized")
            result = self.confidential_app.acquire_token_for_client(
                scopes=self._scopes()
            )
        else:
            if not self.public_app:
                raise RuntimeError("Public client not initialized")
            account = None
            try:
                accounts = self.public_app.get_accounts()
                if accounts:
                    account = accounts[0]
            except Exception:
                account = None

            result = None
            if account:
                result = self.public_app.acquire_token_silent(
                    self._scopes(), account=account
                )

            if not result:
                flow = self.public_app.initiate_device_flow(scopes=self._scopes())
                if "user_code" not in flow:
                    raise RuntimeError(
                        "Device flow creation failed: "
                        f"{json.dumps(flow, ensure_ascii=True)}"
                    )

                print("Sign in with the device code:")
                print(f"  Code: {flow['user_code']}")
                print(f"  URL:  {flow['verification_uri']}")
                print("Waiting for authorization...")

                try:
                    if is_macos() and self.settings.open_browser:
                        url = flow.get("verification_uri_complete") or flow.get(
                            "verification_uri"
                        )
                        if url:
                            import webbrowser

                            webbrowser.open(url)
                except Exception:
                    pass

                result = self.public_app.acquire_token_by_device_flow(flow)

        if not result:
            raise RuntimeError("Token acquisition failed")
        if "access_token" not in result:
            raise RuntimeError(
                f"Auth error: {result.get('error')}: {result.get('error_description')}"
            )

        self._save_cache()
        return result

    def _mailbox_base(self) -> str:
        mailbox = self.settings.mailbox_user.strip() or "me"
        if mailbox.lower() == "me":
            return f"{GRAPH_BASE}/me"
        safe_addr = quote(mailbox)
        return f"{GRAPH_BASE}/users/{safe_addr}"

    @staticmethod
    def _headers(token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get_messages(
        self,
        top: int,
        folder: str,
        recipient: Optional[str],
        unread_only: bool,
    ) -> List[Dict[str, object]]:
        token = self.acquire_token()["access_token"]
        select_fields = [
            "id",
            "subject",
            "isRead",
            "receivedDateTime",
            "from",
            "bodyPreview",
            "body",
        ]
        normalized_recipient = (recipient or "").strip().lower()
        if normalized_recipient:
            select_fields.extend(["toRecipients", "ccRecipients", "bccRecipients"])

        params = {
            "$select": ",".join(select_fields),
            "$orderby": "receivedDateTime desc",
            "$top": str(top),
        }
        if unread_only:
            params["$filter"] = "isRead eq false"

        resp = requests.get(
            f"{self._mailbox_base()}/mailFolders/{folder}/messages",
            headers=self._headers(token),
            params=params,
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Graph error {resp.status_code}: {resp.text}")

        data = resp.json()
        messages = data.get("value", [])
        if normalized_recipient:
            messages = [
                m for m in messages if _message_has_recipient(m, normalized_recipient)
            ]
        return messages


def _message_has_recipient(message: Dict[str, object], normalized: str) -> bool:
    fields = ("toRecipients", "ccRecipients", "bccRecipients")
    for field in fields:
        entries = message.get(field) or []
        if not isinstance(entries, list):
            continue
        for item in entries:
            email_info = item.get("emailAddress") if isinstance(item, dict) else None
            address = ""
            if isinstance(email_info, dict):
                address = email_info.get("address", "") or ""
            if isinstance(address, str) and address.strip().lower() == normalized:
                return True
    return False
