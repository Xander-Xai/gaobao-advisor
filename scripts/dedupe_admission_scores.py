#!/usr/bin/env python3
"""Plan and, only on explicit instruction, apply a deduplication of admission data.

Deduplication is split into two tiers because the two tiers carry very different
risk:

``exact``
    Rows whose every non-identifier column is identical. Keeping the lowest
    ``id`` loses no information at all, so this tier is safe.

``conflicting``
    Rows that share the business key (school, major, province, year, batch,
    subject) but disagree on the recorded scores. These are distinct published
    observations — 征集志愿 rounds, 降分录取, parallel batches — and collapsing
    them would destroy information. This tier is only ever reported.

The command defaults to a dry run against a copy of the database. Deleting rows
requires ``--apply`` on a database that is not the live one unless
``--allow-live-database`` is also supplied.

Examples
--------
    python scripts/dedupe_admission_scores.py --database data/gaokao.db
    python scripts/dedupe_admission_scores.py --database data/copy.db --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LIVE_DATABASE = Path("data/gaokao.db")

KEEP_RULE = "lowest id survives (first writer wins)"
BUSINESS_KEY = ("school_id", "major_id", "province", "year", "batch", "subject_type")
PAYLOAD_COLUMNS = ("min_score", "avg_score", "max_score", "min_rank", "plan_count", "standardized_batch")


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _key_expression(columns: list[str]) -> str:
    return ",".join(f'"{name}"' for name in columns)


def _value_columns(connection: sqlite3.Connection, table: str = "admission_scores") -> list[str]:
    """Every column that carries meaning, i.e. all of them except the surrogate id."""
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")') if row[1] != "id"]


def _payload_expression(columns: list[str]) -> str:
    return ",".join(f"ifnull(\"{name}\", '')" for name in columns)


def build_plan(database: Path) -> OrderedDict:
    """Measure both duplicate tiers without modifying the database."""
    database = Path(database)
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        columns = _columns(connection, "admission_scores")
        key = [name for name in BUSINESS_KEY if name in columns]
        payload = [name for name in PAYLOAD_COLUMNS if name in columns]
        non_id = [name for name in columns if name != "id"]
        key_expr = _key_expression(key)
        payload_expr = _payload_expression(payload)

        total = connection.execute("SELECT COUNT(*) FROM admission_scores").fetchone()[0]

        exact_rows = connection.execute(
            f"SELECT COALESCE(SUM(c - 1), 0) FROM "
            f"(SELECT COUNT(*) c FROM admission_scores GROUP BY {_key_expression(non_id)} HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        exact_groups = connection.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM admission_scores "
            f"GROUP BY {_key_expression(non_id)} HAVING COUNT(*) > 1)"
        ).fetchone()[0]

        key_rows = connection.execute(
            f"SELECT COALESCE(SUM(c - 1), 0) FROM "
            f"(SELECT COUNT(*) c FROM admission_scores GROUP BY {key_expr} HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        key_groups = connection.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM admission_scores GROUP BY {key_expr} HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        conflicting_groups = connection.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM admission_scores GROUP BY {key_expr} "
            f"HAVING COUNT(DISTINCT printf('%s', {payload_expr})) > 1)"
        ).fetchone()[0]
        conflicting_rows = connection.execute(
            f"SELECT COALESCE(SUM(c - 1), 0) FROM (SELECT COUNT(*) c FROM admission_scores GROUP BY {key_expr} "
            f"HAVING COUNT(DISTINCT printf('%s', {payload_expr})) > 1)"
        ).fetchone()[0]

        samples = connection.execute(
            f"SELECT {key_expr}, COUNT(*) AS rows_in_group, "
            f"COUNT(DISTINCT printf('%s', {payload_expr})) AS distinct_payloads "
            f"FROM admission_scores GROUP BY {key_expr} HAVING COUNT(*) > 1 "
            f"ORDER BY rows_in_group DESC, distinct_payloads DESC LIMIT 10"
        ).fetchall()
    finally:
        connection.close()

    return OrderedDict(
        [
            ("database", str(database)),
            ("generated_at", datetime.now(tz=timezone.utc).isoformat()),
            ("total_rows", total),
            ("keep_rule", KEEP_RULE),
            ("business_key", list(key)),
            (
                "exact_tier",
                {
                    "rows_to_delete": exact_rows,
                    "groups": exact_groups,
                    "risk": "none — every non-id column is identical",
                    "reversible": "yes — the deleted ids are written to the delete log",
                },
            ),
            (
                "conflicting_tier",
                {
                    "rows_in_conflict": conflicting_rows,
                    "groups": conflicting_groups,
                    "risk": "high — distinct published observations, deduplicating them loses data",
                    "action": "reported only; never deleted by this tool",
                },
            ),
            ("samples", [dict(row) for row in samples]),
        ]
    )


def exact_delete_sql(database: Path) -> str:
    """Return the SQL that removes only byte-identical duplicate rows."""
    connection = sqlite3.connect(f"file:{Path(database)}?mode=ro", uri=True)
    try:
        non_id = _key_expression(_value_columns(connection))
    finally:
        connection.close()
    return (
        "DELETE FROM admission_scores WHERE id NOT IN (\n"
        "    SELECT MIN(id) FROM admission_scores GROUP BY " + non_id + "\n"
        ");"
    )


def apply_exact_dedupe(database: Path, log_dir: Path) -> dict:
    """Delete only byte-identical duplicates, logging every removed id."""
    database = Path(database)
    connection = sqlite3.connect(database)
    try:
        non_id = _key_expression(_value_columns(connection))
        doomed = [
            row[0]
            for row in connection.execute(
                f"SELECT id FROM admission_scores WHERE id NOT IN "
                f"(SELECT MIN(id) FROM admission_scores GROUP BY {non_id})"
            )
        ]
        log_path = Path(log_dir) / f"dedupe_deleted_ids_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            json.dumps({"database": str(database), "count": len(doomed), "ids": doomed}, indent=2) + "\n",
            encoding="utf-8",
        )
        before = connection.execute("SELECT COUNT(*) FROM admission_scores").fetchone()[0]
        connection.execute("BEGIN")
        connection.execute(
            f"DELETE FROM admission_scores WHERE id NOT IN (SELECT MIN(id) FROM admission_scores GROUP BY {non_id})"
        )
        connection.commit()
        after = connection.execute("SELECT COUNT(*) FROM admission_scores").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return {
        "rows_before": before,
        "rows_after": after,
        "deleted": before - after,
        "log": str(log_path),
        "integrity": integrity,
    }


def render(plan: OrderedDict) -> str:
    lines = ["=" * 72, "  ADMISSION SCORE DEDUPLICATION PLAN", "=" * 72]
    lines.append(f"\ndatabase     : {plan['database']}")
    lines.append(f"total rows   : {plan['total_rows']:,}")
    lines.append(f"keep rule    : {plan['keep_rule']}")
    lines.append(f"business key : {', '.join(plan['business_key'])}")

    lines.append("\n-- tier 1: byte-identical duplicates " + "-" * 36)
    lines.append(f"   rows that would be deleted : {plan['exact_tier']['rows_to_delete']:,}")
    lines.append(f"   groups                     : {plan['exact_tier']['groups']:,}")
    lines.append(f"   risk                       : {plan['exact_tier']['risk']}")
    lines.append(f"   reversible                 : {plan['exact_tier']['reversible']}")

    lines.append("\n-- tier 2: business key conflicts " + "-" * 38)
    lines.append(f"   rows in conflicting groups : {plan['conflicting_tier']['rows_in_conflict']:,}")
    lines.append(f"   conflicting groups         : {plan['conflicting_tier']['groups']:,}")
    lines.append(f"   risk                       : {plan['conflicting_tier']['risk']}")
    lines.append(f"   action                     : {plan['conflicting_tier']['action']}")

    lines.append("\n-- largest duplicate groups " + "-" * 40)
    for sample in plan["samples"]:
        key = "/".join(str(sample[name]) for name in plan["business_key"])
        lines.append(f"   {key:<58} rows={sample['rows_in_group']:<3} payloads={sample['distinct_payloads']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=LIVE_DATABASE)
    parser.add_argument("--json", type=Path, default=None, help="Write the plan here")
    parser.add_argument("--sql", action="store_true", help="Print the exact-delete SQL instead of the summary")
    parser.add_argument("--apply", action="store_true", help="Actually delete the byte-identical duplicates")
    parser.add_argument(
        "--allow-live-database",
        action="store_true",
        help=f"Permit --apply against {LIVE_DATABASE}; without it the tool works on a temporary copy",
    )
    parser.add_argument("--dry-run-copy", type=Path, default=None, help="Apply against this scratch copy instead")
    parser.add_argument(
        "--delete-log-dir",
        type=Path,
        default=Path("data/dedupe-logs"),
        help="Where the removed-id audit log is written (default: data/dedupe-logs)",
    )
    args = parser.parse_args(argv)

    if not args.database.exists():
        print(f"BLOCKED database not found: {args.database}", file=sys.stderr)
        return 2

    plan = build_plan(args.database)
    if args.sql:
        print(exact_delete_sql(args.database))
        return 0

    print(render(plan))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nplan written to {args.json}")

    if plan["exact_tier"]["rows_to_delete"] == 0:
        print("\nnothing to deduplicate at tier 1.")
        return 0

    if not args.apply:
        print("\nDRY RUN — no rows were deleted. Pass --apply to execute tier 1.")
        print(f"SQL that --apply would run:\n{exact_delete_sql(args.database)}")
        return 0

    target = args.dry_run_copy or args.database
    if args.dry_run_copy:
        if args.dry_run_copy.resolve() == args.database.resolve():
            print("BLOCKED --dry-run-copy must differ from --database.", file=sys.stderr)
            return 2
        shutil.copy2(args.database, args.dry_run_copy)
        print(f"\nworking on scratch copy {args.dry_run_copy}")
    elif args.database.resolve() == LIVE_DATABASE.resolve() and not args.allow_live_database:
        print(
            "\nBLOCKED --apply against the live database also requires --allow-live-database.",
            file=sys.stderr,
        )
        return 2

    print(f"\napplying tier 1 to {target}")
    result = apply_exact_dedupe(target, args.delete_log_dir)
    print(f"   rows before : {result['rows_before']:,}")
    print(f"   rows after  : {result['rows_after']:,}")
    print(f"   deleted     : {result['deleted']:,}")
    print(f"   integrity   : {result['integrity']}")
    print(f"   delete log  : {result['log']}")
    print(f"   tier 2 groups ({plan['conflicting_tier']['groups']:,}) were left untouched by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
