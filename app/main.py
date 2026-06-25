from __future__ import annotations

import argparse
import asyncio

from app.comments.generator import CommentGenerator
from app.db.repositories import AccountRepository, ChatRepository, CommentRepository, LogRepository, SettingsRepository
from app.db.supabase_client import get_supabase
from app.logs.logger import AccountLogger
from app.telegram.account_login import onboard_account_cli, test_classic_auth_cli
from app.telegram.account_worker import AccountWorker
from app.telegram.join_manager import JoinManager


async def run_onboarding() -> None:
    db = get_supabase()
    account_repo = AccountRepository(db)
    settings_repo = SettingsRepository(db)
    chat_repo = ChatRepository(db)
    account_id = await onboard_account_cli(account_repo, settings_repo, chat_repo)
    print(f"Аккаунт успешно добавлен: {account_id}")


async def run_auth_test() -> None:
    await test_classic_auth_cli()


async def run_workers() -> None:
    db = get_supabase()
    account_repo = AccountRepository(db)
    settings_repo = SettingsRepository(db)
    chat_repo = ChatRepository(db)
    comments_repo = CommentRepository(db)
    logger = AccountLogger(LogRepository(db))
    generator = CommentGenerator()
    join_manager = JoinManager(chat_repo)

    accounts = account_repo.list_active_accounts()
    tasks = []
    for account in accounts:
        settings = settings_repo.get_settings(account["id"])
        if not settings.get("is_active", True):
            continue
        worker = AccountWorker(
            account=account,
            account_settings=settings,
            chats=chat_repo,
            comments=comments_repo,
            logger=logger,
            generator=generator,
            join_manager=join_manager,
        )
        tasks.append(asyncio.create_task(worker.run()))

    if not tasks:
        print("Активные аккаунты не найдены.")
        return

    await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Мультиаккаунтный Telegram-комментатор")
    parser.add_argument("command", choices=["onboard", "add-account", "run-workers", "test-auth"])
    args = parser.parse_args()

    if args.command in {"onboard", "add-account"}:
        asyncio.run(run_onboarding())
    elif args.command == "test-auth":
        asyncio.run(run_auth_test())
    else:
        asyncio.run(run_workers())


if __name__ == "__main__":
    main()
