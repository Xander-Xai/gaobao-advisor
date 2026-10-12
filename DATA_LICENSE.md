# Data license and provenance

## Dataset in this repository

`scripts/seed_demo_data.py` generates the entire dataset shipped with this demo.

* **Type:** synthetic, machine-generated, deterministic (seed `20240617`)
* **License:** CC0-1.0
* **Contains:** no real institution, programme, score, rank or policy data
* **Markers:** institution names carry `（合成）`; provinces are invented
  (`示例省·甲`…); the `schools.special_type` column carries
  `SYNTHETIC_DEMO_DATA`

Regenerate with:

```bash
python -m scripts.seed_demo_data --db data/demo.db --reset
```

## What is deliberately NOT here

The upstream private project contained a knowledge corpus and a quotation
collection attributed to a named individual, plus production database backups.
None of it is redistributed here. See README "RAG 边界" and "安全规则资产".

If you add a corpus, you must be able to state its licence and provenance.
