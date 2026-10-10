# Data sources and provenance policy

gaobao-advisor separates source-code adapters from the data returned by those
adapters. Inclusion of an adapter does not grant permission to redistribute
the upstream data.

## Source registry

| Source or asset | Repository location | Use | Redistribution status |
| --- | --- | --- | --- |
| Synthetic demo records | `data/sample/` | Local demonstration and tests | CC0 only when explicitly marked synthetic |
| API coverage fixture | `data/api_coverage_test.json` | Automated test fixture | Project MIT license; not admissions data |
| Local import checkpoint | `data/checkpoint_plans.json` | Resume internal import jobs | Excluded as runtime state |
| Baidu Gaokao / China Education Online adapter | `scrapers/baidu_gaokao.py` | Optional external lookup/import | Adapter code may be distributed; returned data is not bundled or relicensed |
| Baidu search fallback | `scrapers/baidu.py` | Optional discovery fallback | Snippets and results are not bundled for redistribution |
| Official examination authorities and university notices | Referenced by prompts and documentation | Recommended verification sources | Links and factual citations only; source publications keep their own rights |
| Knowledge and quote collections | `knowledge/` | Internal RAG content | Excluded pending item-level provenance and permission review |
| Prompt and research collections | `prompts/`, `memory/` | Internal development material | Excluded from the public source distribution |

## Required provenance fields

Every future distributable data asset must record:

- stable asset name and repository path;
- source publisher and source URL;
- access or publication date;
- applicable license or written permission;
- allowed modification and redistribution scope;
- covered province, year and admissions batch where relevant;
- personal-information assessment;
- checksum and transformation steps.

An asset without all applicable fields is classified as `exclude`.

## Runtime source labels

Application output that contains a score, rank, enrollment plan, salary or
employment statistic must retain the source and year. If only one non-official
source is available, the result must say that it is unverified and direct the
user to the relevant provincial examination authority or official university
notice.

## Reporting provenance problems

Use a GitHub issue for non-sensitive source corrections. Do not attach database
dumps, applicant profiles or private correspondence. For sensitive provenance
or privacy problems, follow `SECURITY.md`.
