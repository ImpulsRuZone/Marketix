#!/usr/bin/env python3
"""Convert Supabase comments INSERT dump to a readable CSV (comments_readable layout)."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

COLUMNS = (
    "sent_at_moscow",
    "account_name",
    "chat_title",
    "post_text",
    "generated_comment",
    "status",
    "sent_comment",
    "error_message",
)

MOSCOW = ZoneInfo("Europe/Moscow")


def _skip_ws(blob: str, idx: int) -> int:
    while idx < len(blob) and blob[idx] in " \t\n\r":
        idx += 1
    return idx


def _parse_value(blob: str, idx: int) -> tuple[str | None, int]:
    idx = _skip_ws(blob, idx)
    if idx >= len(blob):
        return None, idx
    if blob.startswith("null", idx):
        return None, idx + 4
    if blob[idx] != "'":
        raise ValueError(f"Expected string at position {idx}: {blob[idx : idx + 20]!r}")

    idx += 1
    chars: list[str] = []
    while idx < len(blob):
        ch = blob[idx]
        if ch == "'":
            if idx + 1 < len(blob) and blob[idx + 1] == "'":
                chars.append("'")
                idx += 2
                continue
            idx += 1
            break
        chars.append(ch)
        idx += 1
    return "".join(chars), idx


def parse_insert_rows(sql: str) -> list[list[str | None]]:
    match = re.search(r"VALUES\s+(.+);\s*$", sql, re.DOTALL)
    if not match:
        raise ValueError("INSERT ... VALUES block not found")

    blob = match.group(1)
    rows: list[list[str | None]] = []
    idx = 0

    while True:
        idx = _skip_ws(blob, idx)
        if idx >= len(blob) or blob[idx] != "(":
            break

        idx += 1
        record: list[str | None] = []
        while True:
            value, idx = _parse_value(blob, idx)
            record.append(value)
            idx = _skip_ws(blob, idx)
            if idx < len(blob) and blob[idx] == ",":
                idx += 1
                continue
            if idx < len(blob) and blob[idx] == ")":
                idx += 1
                break
            raise ValueError(f"Unexpected token at {idx}: {blob[idx : idx + 30]!r}")

        rows.append(record)
        idx = _skip_ws(blob, idx)
        if idx < len(blob) and blob[idx] == ",":
            idx += 1
            continue
        break

    return rows


def format_sent_at_moscow(sent_at: str | None) -> str:
    if not sent_at:
        return ""
    normalized = sent_at.replace("+03", "+03:00")
    dt = datetime.fromisoformat(normalized)
    return dt.astimezone(MOSCOW).strftime("%d.%m.%Y %H:%M:%S")


def to_readable_rows(raw_rows: list[list[str | None]]) -> list[dict[str, str]]:
    readable: list[dict[str, str]] = []
    for row in raw_rows:
        (
            _id,
            _account_id,
            _chat_id,
            _post_id,
            post_text,
            generated_comment,
            sent_comment,
            status,
            error_message,
            _created_at,
            sent_at,
            _updated_at,
            account_name,
            chat_title,
        ) = row

        readable.append(
            {
                "sent_at_moscow": format_sent_at_moscow(sent_at),
                "account_name": account_name or "",
                "chat_title": chat_title or "",
                "post_text": post_text or "",
                "generated_comment": generated_comment or "",
                "status": status or "",
                "sent_comment": sent_comment or "",
                "error_message": error_message if status == "failed" else "",
            }
        )
    return readable


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sql_file",
        type=Path,
        help="SQL dump with INSERT INTO comments ... VALUES",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("exports/neurocommenting/neurocommenting_table.csv"),
        help="Output CSV path",
    )
    args = parser.parse_args()

    sql = args.sql_file.read_text(encoding="utf-8")
    raw_rows = parse_insert_rows(sql)
    readable_rows = to_readable_rows(raw_rows)
    write_csv(readable_rows, args.output)
    print(f"Wrote {len(readable_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
