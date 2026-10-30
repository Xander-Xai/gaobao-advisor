"""Generate a PBKDF2 password hash for administrator configuration.

Usage::

    python scripts/hash_admin_password.py            # interactive prompt
    python scripts/hash_admin_password.py --password '...' --json

The plaintext password is never written to disk by this script. Prefer the
interactive prompt so the value does not end up in shell history.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys

from server.admin.auth import hash_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hash an administrator password")
    parser.add_argument("--password", default="", help="plaintext password (prefer interactive prompt)")
    parser.add_argument("--username", default="operator", help="username for the --json output")
    parser.add_argument("--role", default="operator", choices=["viewer", "operator", "admin"])
    parser.add_argument("--iterations", type=int, default=600_000)
    parser.add_argument("--json", action="store_true", help="print an ADMIN_USERS_JSON entry")
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("password must be at least 8 characters", file=sys.stderr)
        return 2
    try:
        encoded = hash_password(password, iterations=args.iterations)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                [{"username": args.username, "password_hash": encoded, "role": args.role}],
                ensure_ascii=False,
            )
        )
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
