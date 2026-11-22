# Course report and completion record

- [DSC5003-report.pdf](DSC5003-report.pdf): 15-page English technical report, including four portrait figures, tables, methods, validation, limitations, references, and deliverable information.
- [Markdown copy](DSC5003-report.md) and [standalone HTML](DSC5003-report.html): reviewable text and a portable preview with embedded figures.
- [Structured report](report.json) and [builder](build_report.py): reproducible source for the generated documents.
- [Evidence registry](evidence_registry.json): report blocks mapped to source/result files and SHA-256 hashes.
- [Delivery validation](delivery_validation.json): PDF content, layout, evidence, and link checks, with explicit pending fields.
- [Environment verification](environment_verification.json): successful fresh offline wheel installation for plotting and PDF checks.

## Information that still requires the team

Edit [team_metadata.json](team_metadata.json) to provide the actual data:

```json
{
  "members": [
    {"name": "Actual member name", "undergraduate_major": "Actual undergraduate major"}
  ],
  "contributions": [
    {"name": "Actual member name", "actual_contribution": "What this person actually did"}
  ]
}
```

The example is a schema illustration, not a real team member or contribution.
No number of members, identities, author order, or individual roles has been
inferred. The submission deadline and any updated course instructions were not
provided. The supplied project slides are labeled tentative. The report retains
a technical-draft banner pending team details and human scientific review.

Video production, video-link insertion, and submission are excluded from the
current task. No upload, commit, push, or course submission was performed.

## Rebuild

The experiment inputs/results must already exist. Core experiments require only
Python's standard library; report figures and PDF checks use Python 3.12:

```bash
uv venv .venv_report --python 3.12
uv pip install --python .venv_report/bin/python -r requirements_report.txt
.venv_report/bin/python scripts/report_figures.py
python3 report/build_report.py

# Native macOS renderer; no LaTeX or browser is needed.
swift report/render_pdf.swift report/report.json report/DSC5003-report.pdf
.venv_report/bin/python report/normalize_pdf.py
.venv_report/bin/python report/check_delivery.py
```

The report uses the actual result CSVs. Narrative changes belong in
`build_report.py`; `report.json`, Markdown, and HTML are generated copies and will
be overwritten by the builder. Metadata changes can be made in
`team_metadata.json` before rebuilding. Human-review and submission-ready states
are never automatically promoted by the build.

If the host restricts system caches, set `MPLCONFIGDIR`, `PYTHONPYCACHEPREFIX`,
and the Swift module-cache path to writable temporary directories. No packages
or runtime configuration need to be installed globally.

## Reproduction scope

The complete parameter grid was repeated in a fresh source tree and empty venv:
26 tests, all 120 fixed-baseline rows, all 1,680 grid rows, and 75 resource jobs
passed their applicable correctness/signature checks. See
[full reproduction verification](../results/full_reproduction_verification.json).
Timing and RSS values are not expected to match exactly across repeats.

Report plotting packages were installed into a separate fresh environment from
cached wheels, with successful imports and figure generation. This was an actual
installation rather than reuse of the earlier symlinked environment.
Cold external downloads/online dependency resolution were attempted but could
not be verified because this execution host failed DNS resolution. The public
source downloader and exact requirement pins remain documented; the report does
not claim a successful cold network test.

## Review and provenance

The report includes the original paper, reference repository, course slides, and
an acknowledgment of the research-writing procedural reference. Bibliographic
metadata for the replicated paper were checked against its supplied PDF. AI
assistance is disclosed as work performed in this workspace; individual human
credit and course policy compliance must be confirmed by the team.

Machine provenance and layout checks are not human verification. Dataset-specific
usage terms and the exact original data/software revision remain the documented
research limitations. The raw benchmarks and upstream code are not redistributed
in this report directory.
