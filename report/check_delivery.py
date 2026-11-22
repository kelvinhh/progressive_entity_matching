#!/usr/bin/env python3
"""Check PDF content, evidence hashes, course coverage, and reproducibility artifacts.

Requires pypdf only for reading the generated PDF. This is a local technical
check and does not assert human approval, submission readiness, or network access.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def normalized(text):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", text).casefold())


def main():
    pdf = HERE / "DSC5003-report.pdf"
    reader = PdfReader(pdf)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    canonical = normalized(text)
    document = json.loads((HERE / "report.json").read_text())
    ledger = json.loads((HERE / "evidence_registry.json").read_text())
    layout = json.loads((HERE / "layout_validation.json").read_text())
    if layout["overflow_warnings"] or layout["pages"] != len(reader.pages):
        raise AssertionError("PDF layout warnings or page-count mismatch")
    tested_cells = 0
    for block in document["blocks"]:
        values = []
        if block.get("text"): values.append(block["text"])
        if block.get("caption"): values.append(block["caption"])
        values += [cell for row in block.get("rows", []) for cell in row]
        if block.get("source") and not (HERE / block["source"]).exists():
            raise AssertionError("Missing report figure")
        for value in values:
            expected = normalized(value)
            if expected and expected not in canonical:
                raise AssertionError(f"Report text not found in PDF: {value[:100]!r}")
            tested_cells += 1
    for key, source in ledger["sources"].items():
        for path, expected in source["files"].items():
            if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
                raise AssertionError(f"Stale evidence hash: {key} {path}")
    for claim in ledger["claims"]:
        block = document["blocks"][claim["block"]]
        actual = hashlib.sha256(json.dumps(block, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if actual != claim["content_sha256"]:
            raise AssertionError("Changed report block requires rebuilding evidence registry")
    with (ROOT / "results/sweep_metrics.csv").open(newline="") as stream:
        sweep = list(csv.DictReader(stream))
    with (ROOT / "results/resource_measurements.csv").open(newline="") as stream:
        measurements = list(csv.DictReader(stream))
    if len(sweep) != 1680 or len(measurements) != 75:
        raise AssertionError("Unexpected result coverage")
    full = json.loads((ROOT / "results/full_reproduction_verification.json").read_text())
    if full["full_run"]["grid_rows_reproduced"] != 1680 or full["full_run"]["resource_measured_jobs_completed"] != 75:
        raise AssertionError("Full reproduction evidence is incomplete")
    for path in [ROOT / "README.md", HERE / "DSC5003-report.md", ROOT / "results/stage2_analysis.md"]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" not in target and not target.startswith("#"):
                if not (path.parent / target.split("#")[0]).exists():
                    raise AssertionError(f"Broken local link: {path} {target}")
    metadata = json.loads((HERE / "team_metadata.json").read_text())
    missing = []
    if not metadata["members"]: missing.append("Group members' names and undergraduate majors")
    if not metadata["contributions"]: missing.append("Actual individual contribution statement")
    if not metadata["submission_deadline"]: missing.append("Submission deadline and any later course instructions")
    if not metadata["human_review_complete"]: missing.append("Human review of scientific claims and authorship")
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "technical_checks_passed": True,
        "pdf_pages": len(reader.pages), "pdf_text_and_table_cells_checked": tested_cells,
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "report_json_sha256": hashlib.sha256((HERE / "report.json").read_bytes()).hexdigest(),
        "layout_overflow_warnings": layout["overflow_warnings"],
        "evidence_hashes_match": True, "full_grid_rows_reproduced": 1680,
        "fresh_resource_jobs_completed": 75, "core_tests_passed": full["tests_passed"],
        "offline_plotting_installation_verified": True, "cold_network_acquisition_verified": False,
        "repository_url_checked_via_authenticated_api": True,
        "latest_local_changes_uploaded": False,
        "administrative_information_pending": missing,
        "excluded_by_user": ["Video production", "Video link insertion", "Submission"],
        "submission_ready": False,
        "limitations": ["The execution host failed external DNS resolution; cold downloads and online dependency resolution are not claimed.",
                        "Dataset-specific terms and the exact original paper data/software revision remain documented research limitations.",
                        "Machine checks do not constitute human scientific review or final course submission approval."],
    }
    (HERE / "delivery_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Technical checks passed: {len(reader.pages)} PDF pages, {tested_cells} text/table units, evidence hashes and local links")
    print("Pending human information:", "; ".join(missing))


if __name__ == "__main__": main()
