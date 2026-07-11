# Data licensing

The MIT license in `LICENSE` applies only to source code and documentation that
the gaobao-advisor contributors have the right to license. It does not grant a
license to third-party datasets, imported records, quotations, images, model
outputs, or user-generated content.

## Synthetic demo data

Files placed under `data/sample/` and explicitly marked as synthetic are made
available under the Creative Commons CC0 1.0 Universal dedication. They must
not represent real applicants, real admission outcomes, or authoritative
admission data.

CC0 text: <https://creativecommons.org/publicdomain/zero/1.0/legalcode>

## Code-adjacent test fixtures

`data/api_coverage_test.json` is a project-authored test fixture and is covered
by the repository MIT license. It is not admissions data.

## Excluded data

No license is granted for any of the following unless a file carries a separate
written license from its rights holder:

- imported university, major, score, rank, enrollment, employment or salary
  records;
- database files, SQL archives, reports, logs, analytics or conversation data;
- cached responses, embeddings, checkpoints or generated model output;
- third-party quotations, interview transcripts, articles, images or logos;
- files classified as `exclude` in `config/open_source_assets.tsv`.

These assets are not part of the public source distribution. Operators are
responsible for confirming that data they import may be collected, processed
and redistributed in their jurisdiction and deployment context.

## Contributions

Do not contribute data unless the pull request identifies its source, rights
holder, applicable license or permission, collection date, allowed uses, and
whether it contains personal information. “Publicly accessible” does not mean
“licensed for redistribution.”
