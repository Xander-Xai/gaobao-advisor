# Demo mode contract

This document defines what "demo mode" means, what the backend must do when it
is active, and how CI proves the claim. It exists because a disclosure that is
not backed by actual behavior is worse than no disclosure: it trains users to
trust a label.

## 1. The three runtime modes

The application distinguishes three runtime configurations. They differ in data
source, provider, and what the user is told.

| Mode | Trigger | Data | Model | Disclosure |
|---|---|---|---|---|
| **demo** | `LLM_PROVIDER=demo` | Synthetic records seeded from `data/sample/demo_admissions.json` | None. `server/graph/nodes/llm_node._demo_reply()` returns a fixed string. | Yes, mandatory. See §3. |
| **formal data** | `LLM_PROVIDER` set to a real provider + a populated database | Operator-imported records | Remote provider | Operator-supplied, not shipped |
| **offline** | Real provider configured but unreachable, or `ENABLE_RAG_KB=false` with no vector index | Whatever is in the database | Fallback reply from `tuning.yaml` | A degraded notice, not the demo notice |

`mode` in the health payload is `"demo"` only when `LLM_PROVIDER` is `demo`;
otherwise it reports `APP_ENV`. This is deliberate: a real deployment must never
be able to look like a demo to avoid scrutiny, and a demo must never look like a
real deployment.

## 2. Health endpoint schema

`GET /api/v1/health` returns:

```json
{
  "status": "ok",
  "version": "3.1.0",
  "database": "connected",
  "mode": "demo",
  "llm_provider": "demo",
  "optional_services": { "rag": "disabled", "voice": "disabled" }
}
```

`optional_services` reflects `ENABLE_RAG_KB` and `VOICE_ENABLED`. The demo
configuration in `docker-compose.yml` sets both to `false`, so the demo runs
with no key, no remote model, no vector store and no speech service.

`database` reports engine connectivity (`SELECT 1`). It deliberately does **not**
claim the schema is populated. A demo container does create the schema and seed
synthetic rows, so the field is accurate for the shipped configuration; for an
arbitrary empty database the data-quality command is the authority, not this
field.

## 3. Disclosure rules

`server/routes/chat.py` defines the demo disclosure:

> 【社区演示模式】当前内容仅用于展示软件流程，数据均为合成示例；本项目是非官方工具，不能用于真实志愿决策。

The demo reply path prefixes every token stream with this string, so the user
always sees it. Three markers must be present in any demo reply, and CI asserts
each one:

| Marker | Meaning |
|---|---|
| `演示模式` | this is a demonstration, not a service |
| `合成` | the data is synthetic |
| `非官方` | this project is not affiliated with any authority |

## 4. The synthetic dataset must actually be synthetic

`data/sample/demo_admissions.json` is the only dataset allowed into the image
(`.dockerignore` re-includes `data/sample/` after excluding `data/`). It is
required to be self-describing:

```json
{
  "metadata": {
    "synthetic": true,
    "license": "CC0-1.0",
    "warning": "全部内容为合成演示数据，不代表任何真实学校、考生或录取结果，不得用于真实志愿决策。"
  }
}
```

Every school is a fictional entity (`北辰示例科技大学（合成）`, `海岳示例师范学院（合成）`,
`云帆示例职业大学（合成）`) located in a fictional province (`示例省`). Every row
carries `data_source_note = "SYNTHETIC DEMO DATA - NOT FOR REAL ADMISSION DECISIONS"`.
`scripts/seed_demo_data.py` refuses to run if the `synthetic` marker is missing,
and is idempotent.

`tests/test_demo_seed.py` asserts all of this, including that no real institution
name (`清华大学`, `北京大学`, `复旦大学`) appears in the seeded database.

## 5. Backend behavior must match the disclosure

The disclosure says the data is synthetic. Two behaviors are therefore required:

1. **No real-data path is reachable in demo mode.** The demo database contains
   only fictional records, so a query can only ever match fictional data.
2. **Missing data is reported as missing.** When a user asks about a real
   province (for example `河北`) that does not exist in the synthetic dataset,
   the pipeline must say so rather than inventing a school.

Verified behavior with `我是河北物理类考生，考了600分，想报计算机` against the demo
database:

```
events: slots → emotion → structured → token… → quality → done
rank_info.provenance_status : unverified
rank_info.message           : 暂无河北 2025年物理的位次数据（建议查省考试院）
advice                      : （数据来源待补全，无法验证）
```

The system reports that it has no data for that province. This is the correct
behavior and is asserted by
`tests/test_business_smoke.py::TestEmptyAndIncompleteData`.

## 6. What CI checks

The `container-smoke` job:

1. `docker compose up --detach --build api frontend` with `.env.example` copied
   to `.env` — no keys present anywhere.
2. Polls `/api/v1/health` and asserts `status == ok`, `mode == demo`, and
   `optional_services == {"rag": "disabled", "voice": "disabled"}`.
3. Requests the frontend shell from `http://localhost:3080/`.
4. Opens an SSE chat request and asserts the reply contains `演示模式`, `合成`
   and `非官方`.

`tests/test_business_smoke.py::TestRuntimeConfigurationDifference` additionally
proves that a non-demo provider reports `APP_ENV` instead of `demo`, and that
enabling RAG/voice flips `optional_services` to `enabled`.

## 7. What this contract does not cover

- Demo mode is not a sandbox. It disables remote services by configuration, not
  by a security boundary. Do not run it with real keys present.
- The synthetic dataset is tiny (3 schools, 3 majors, 6 score rows, one
  fictional province). It demonstrates the shape of the pipeline, not its
  coverage.
- The freshness check treats the demo's sentinel year `2099` as fresh. That is
  acceptable for a dataset that is explicitly marked synthetic, and the
  data-quality report is intended for real datasets.

## 8. Reproducing

```bash
python scripts/seed_demo_data.py --database /tmp/demo.db
GAOBAO__DB_PATH=/tmp/demo.db LLM_PROVIDER=demo ENABLE_RAG_KB=false VOICE_ENABLED=false \
  uvicorn server.main:app --port 8000
curl -s http://localhost:8000/api/v1/health
curl -sN -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-1","message":"请给我一个演示"}' \
  http://localhost:8000/api/v1/chat
```
