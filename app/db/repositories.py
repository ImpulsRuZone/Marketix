from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client


class AccountRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def upsert_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.db.table("accounts").upsert(payload).execute()
        return response.data[0]

    def list_active_accounts(self) -> list[dict[str, Any]]:
        response = (
            self.db.table("accounts")
            .select("*")
            .eq("status", "active")
            .order("created_at")
            .execute()
        )
        return response.data

    def get_account(self, account_id: str) -> dict[str, Any]:
        response = self.db.table("accounts").select("*").eq("id", account_id).limit(1).execute()
        if not response.data:
            raise ValueError(f"Account not found: {account_id}")
        return response.data[0]


class SettingsRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def upsert_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.db.table("account_settings").upsert(payload).execute()
        return response.data[0]

    def get_settings(self, account_id: str) -> dict[str, Any]:
        response = (
            self.db.table("account_settings")
            .select("*")
            .eq("account_id", account_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ValueError(f"Settings not found for account: {account_id}")
        return response.data[0]


class ChatRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def upsert_target_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.db.table("target_chats").upsert(payload).execute()
        return response.data[0]

    def upsert_account_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.db.table("account_chats").upsert(payload).execute()
        return response.data[0]

    def list_account_chats(self, account_id: str) -> list[dict[str, Any]]:
        response = (
            self.db.table("account_chats")
            .select("id,status,target_chats(id,chat_url,chat_id,title,kind,is_active)")
            .eq("account_id", account_id)
            .eq("target_chats.is_active", True)
            .execute()
        )
        return response.data


class CommentRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def create_comment(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.db.table("comments").insert(payload).execute()
        return response.data[0]

    def update_comment_status(
        self,
        comment_id: str,
        status: str,
        sent_comment: str | None = None,
        error_message: str | None = None,
    ) -> None:
        update_payload: dict[str, Any] = {
            "status": status,
            "error_message": error_message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if sent_comment:
            update_payload["sent_comment"] = sent_comment
            update_payload["sent_at"] = datetime.now(timezone.utc).isoformat()
        self.db.table("comments").update(update_payload).eq("id", comment_id).execute()

    def count_today_sent_comments(self, account_id: str, day_start_iso: str) -> int:
        response = (
            self.db.table("comments")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .eq("status", "sent")
            .gte("sent_at", day_start_iso)
            .execute()
        )
        return response.count or 0


class LogRepository:
    def __init__(self, db: Client) -> None:
        self.db = db

    def write(
        self,
        account_id: str,
        level: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.db.table("logs").insert(
            {
                "account_id": account_id,
                "level": level,
                "event_type": event_type,
                "message": message,
                "payload": payload or {},
            }
        ).execute()
