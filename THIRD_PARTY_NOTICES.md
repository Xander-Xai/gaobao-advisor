# Third-party notices

This repository depends on third-party Python and Node packages. Their licences
apply as stated in each package; nothing here overrides them.

## Verifying

```bash
pip install pip-licenses && pip-licenses --format=markdown
cd frontend && npm ls --all
```

CI runs `pip-audit` and `npm audit --omit=dev` to check for known
vulnerabilities in the locked dependency set.

## Content

No third-party *content* (text corpora, quotations, datasets, images of
third-party origin) is redistributed. The dataset is fully synthetic; see
[`DATA_LICENSE.md`](DATA_LICENSE.md).

## Upstream origin (early MIT-era code)

This project began from an early, **MIT-licensed** version of the upstream
project [`ziqihe10-droid/xuefeng-agent`](https://github.com/ziqihe10-droid/xuefeng-agent).

- The upstream project was MIT-licensed up to and including commit
  `58167355ea3011e1c227a5b2cfe16003125d4dfb` (2026-06-20). It was then relicensed
  to AGPL-3.0 (from commit `0765f8b3c2e0a69991fcd547b6112e98e1a42b14`).
- This repository inherits **only the MIT-era code/content**. The original MIT
  copyright notice — `Copyright (c) 2026 雪峰Agent Contributors` — is preserved
  in [`LICENSE`](LICENSE).
- **No AGPL-3.0-era upstream code is included.** A blob-level comparison against
  the upstream AGPL-era additions found zero shared objects.
- Restricted upstream assets (real admissions databases, raw conversation
  sessions, persona/prompt/knowledge corpora) were **not** carried over; the
  dataset shipped here is fully synthetic (see [`DATA_LICENSE.md`](DATA_LICENSE.md)).
- Subsequent LangGraph / FastAPI / Vue 3 / containerisation / session-security /
  test work in this repository is original to this project, not a copy of later
  upstream code.

## Trademarks and persons

No real individual's name, likeness, methodology, quotations or communication
style is included or imitated. The persona-related assets in the upstream
private project were deliberately removed; see README.
