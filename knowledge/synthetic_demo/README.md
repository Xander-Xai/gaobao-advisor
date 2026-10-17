# SYNTHETIC_DEMO knowledge corpus

This directory is the **original, machine-authored, synthetic** knowledge corpus
that ships with the public demo. It exists so that the RAG (retrieval augmented
generation) subsystem has something real and testable to retrieve from without
redistributing anyone else's content.

## What it is

* **Original** — every sentence here was written for this repository. It is not
  copied from any book, course, article, admission brochure or quotation
  collection.
* **Synthetic** — the institutions, provinces, numbers and "policies" are
  invented placeholders. Institution names carry the `（合成）` marker and match
  the fictional schools produced by `scripts/seed_demo_data.py`.
* **Marked** — every `groups/*.md` file starts with the `SYNTHETIC_DEMO` notice
  line, and `manifest.json` records the corpus marker and version. The
  integrity check in `server/services/rag.py` refuses to serve a corpus whose
  marker is missing.

## What it is NOT

* It is **not** real admission policy, real cut-off lines, real school rankings
  or real career advice. Do not use it to make an education decision.
* It is **not** a redistribution of any upstream private corpus, a named
  person's methodology, or a quotation collection. That material was removed
  from the public demo and stays removed.

## Licence

Released with the rest of the synthetic demo data under **CC0-1.0** — see
[`DATA_LICENSE.md`](../../DATA_LICENSE.md).

## Layout

```
knowledge/synthetic_demo/
  manifest.json            corpus marker, version, file inventory
  README.md                this file
  groups/
    G1_core_method.md            core volunteer-application method
    G2_major_school.md           majors and institutions
    G3_career_future.md          employment outlook
    G4_life_planning.md          life and city planning
    G5_data_format.md            data credibility and output format
    G6_quick_ref.md              quick reference tables
    G7_employment_paths.md       stable employment paths
    G8_graduate_and_vocational.md postgraduate & vocational routes
```

The `G9_*` persona-methodology group that existed in an upstream private project
is deliberately **absent**. `KbRetriever` and the integrity check treat its
absence as intentional, not as an error.
