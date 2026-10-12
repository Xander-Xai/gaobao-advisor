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

## Trademarks and persons

No real individual's name, likeness, methodology, quotations or communication
style is included or imitated. The persona-related assets in the upstream
private project were deliberately removed; see README.
