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

This project continues from an early, **MIT-licensed** version of the upstream
project ([GitHub](https://github.com/ziqihe10-droid/xuefeng-agent)).

- Upstream was MIT-licensed up to and including commit
  `58167355ea3011e1c227a5b2cfe16003125d4dfb` (2026-06-20), and was relicensed to
  AGPL-3.0 from commit `0765f8b3c2e0a69991fcd547b6112e98e1a42b14` (2026-06-20).
- This repository continues from the **MIT-era** code only. The original MIT
  copyright and permission notice is preserved verbatim in [`LICENSE`](LICENSE),
  which is the single canonical copy (not duplicated here).
- Scope of the AGPL check: a blob-level comparison of the revisions and
  differences reviewed found no upstream code added after the relicensing. This
  conclusion is bounded by the revisions compared; it is **not** a legal
  certification of every possible form of code provenance.
- Restricted upstream assets (real admissions databases, raw conversation
  sessions, persona/prompt/knowledge corpora) were **not** carried over; only
  synthetic data ships here (see [`DATA_LICENSE.md`](DATA_LICENSE.md)).
- Subsequent LangGraph / FastAPI / Vue 3 / containerisation / session-security /
  test work in this repository is original to this project, not a copy of later
  upstream code.

## Trademarks and persons

No real individual's name, likeness, methodology, quotations or communication
style is included or imitated. The persona-related assets in the upstream
private project were deliberately removed; see README.
