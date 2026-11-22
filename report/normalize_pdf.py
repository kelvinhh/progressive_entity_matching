#!/usr/bin/env python3
"""Normalize native CoreGraphics PDF cross references without changing page content."""
from pathlib import Path
from pypdf import PdfReader, PdfWriter

path = Path(__file__).resolve().parent / "DSC5003-report.pdf"
reader = PdfReader(path)
writer = PdfWriter()
writer.clone_document_from_reader(reader)
temporary = path.with_suffix(".pdf.tmp")
with temporary.open("wb") as stream:
    writer.write(stream)
temporary.replace(path)
print("Normalized PDF cross references")
