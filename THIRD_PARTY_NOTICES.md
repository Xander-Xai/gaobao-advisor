# Third-party notices and distribution exclusions

The repository depends on third-party packages declared in `pyproject.toml`,
`requirements.lock`, `frontend/package.json` and `frontend/package-lock.json`.
Those packages remain subject to their own licenses; the project MIT license
does not replace them. Dependency-license compatibility is a release gate.

## Asset disposition

| Asset | Classification | Public distribution decision |
| --- | --- | --- |
| `knowledge/` | Mixed summaries, quotations and material derived from public talks, interviews and reports | Exclude until each item has provenance and a redistribution basis |
| `knowledge/quotes/zhangxuefeng_originals.json` | Quotations attributed to a third-party personality or programme | Exclude; attribution alone is not redistribution permission |
| `knowledge/groups/G9_zhangxuefeng_methodology_origin.md` | Third-party-personality research and synthesis | Exclude pending rights and non-affiliation review |
| `prompts/` | Project and derived prompt material | Exclude from the initial public source package pending review |
| `memory/` | Internal research notes | Exclude from the public source package |
| `skills/gaokao/*.md` | Methodology content derived from internal and third-party research | Exclude pending item-level provenance review |
| `content_scripts/` | Internal editorial and marketing material | Exclude from the public source package |
| `frontend/src/assets/vite.svg` | Vite name/logo asset | Exclude until upstream logo and trademark terms are recorded |
| `frontend/src/assets/vue.svg` | Vue name/logo asset | Exclude until upstream logo and trademark terms are recorded |
| `frontend/src/assets/hero.png` | Visual asset without a recorded provenance entry | Exclude pending provenance and privacy review |
| `frontend/public/favicon.svg` | Project visual asset without a recorded provenance entry | Exclude pending maintainer confirmation |
| `frontend/public/icons.svg` | Project visual asset without a recorded provenance entry | Exclude pending maintainer confirmation |
| `demo-preview.gif` | Application screenshot/demo | Exclude pending privacy and embedded-asset review |
| `frontend/src/design/prototypes/*-preview.png` | Local design preview screenshots | Exclude pending provenance and privacy review |

The machine-readable policy in `config/open_source_assets.tsv` is authoritative
for automated checks. A path marked `exclude` may remain in the private working
repository while preparation is in progress, but it must not be present in the
final public source archive.

## Names and factual references

Names of providers, products, schools, public authorities and personalities
may appear solely to identify integrations, sources or subjects of commentary.
Such references do not imply sponsorship, endorsement or official status. See
`TRADEMARKS.md`.
