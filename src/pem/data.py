"""Validated CSV inputs; record IDs are never included in matching text."""
from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Record:
    id: str
    text: str


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def read_records(path: Path, id_column: str, text_columns: list[str],
                 delimiter: str = ",") -> list[Record]:
    if not text_columns or id_column in text_columns:
        raise ValueError("Select non-ID text columns explicitly")
    records = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        if not {id_column, *text_columns} <= set(reader.fieldnames or []):
            raise ValueError(f"Missing CSV columns in {path}")
        for row in reader:
            identifier = (row[id_column] or "").strip()
            if not identifier or identifier in seen:
                raise ValueError(f"Empty or duplicate record ID in {path}: {identifier!r}")
            seen.add(identifier)
            records.append(Record(identifier, normalize(" ".join(row[c] or "" for c in text_columns))))
    return records


def read_truth(path: Path, left_ids: set[str], right_ids: set[str],
               mode: str, delimiter: str = ",") -> set[tuple[str, str]]:
    """Ground truth is an explicit list of positive pairs, not a labeled mixed table."""
    truth = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        if not {"left_id", "right_id"} <= set(reader.fieldnames or []):
            raise ValueError("Ground truth needs left_id,right_id columns")
        for row in reader:
            left, right = row["left_id"].strip(), row["right_id"].strip()
            if left not in left_ids or right not in right_ids:
                raise ValueError(f"Unknown ground-truth record: {(left, right)}")
            if mode == "deduplication":
                if left == right:
                    raise ValueError("Ground truth cannot contain self-pairs")
                left, right = sorted((left, right))
            truth.add((left, right))
    if not truth:
        raise ValueError("Evaluation requires at least one ground-truth match")
    return truth
