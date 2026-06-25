from __future__ import annotations

import argparse
import asyncio

from app.comments.generator import CommentGenerator
from app.db.repositories import AccountRepository, ChatRepository, CommentRepository, LogRepository, SettingsRepository
from app.db.supabase_client import get_supabase
from app.logs.logger import AccountLogger
from app.telegram.account_login import onboard_account_cli
from app.telegram.account_worker import AccountWorker


async def run_onboarding() -> None:
    db = get_supabase()
    account_repo = AccountRepository(db)
    settings_repo = SettingsRepository(db)
    chat_repo = ChatRepository(db)
    account_id = await onboard_account_cli(account_repo, settings_repo, chat_repo)
    print(f"Account onboarded successfully: {account_id}")


async def run_workers() -> None:
    db = get_supabase()
    account_repo = AccountRepository(db)
    settings_repo = SettingsRepository(db)
    comments_repo = CommentRepository(db)
    logger = AccountLogger(LogRepository(db))
    generator = CommentGenerator()

    accounts = account_repo.list_active_accounts()
    tasks = []
    for account in accounts:
        settings = settings_repo.get_settings(account["id"])
        if not settings.get("is_active", True):
            continue
        worker = AccountWorker(account, settings, comments_repo, logger, generator)
        tasks.append(asyncio.create_task(worker.run()))

    if not tasks:
        print("No active accounts found.")
        return

    await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-account Telegram commenter")
    parser.add_argument("command", choices=["onboard", "run-workers"])
    args = parser.parse_args()

    if args.command == "onboard":
        asyncio.run(run_onboarding())
    else:
        asyncio.run(run_workers())


if __name__ == "__main__":
    main()
