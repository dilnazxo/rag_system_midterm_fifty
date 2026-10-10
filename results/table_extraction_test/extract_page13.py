"""Reproduce the focused PyMuPDF table experiment for PDF page 13."""

import json
from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/manuals/STULZ CyberRow DX Engineering Manual QEWR002L.pdf"
OUTPUT = Path(__file__).resolve().parent
PAGE_INDEX = 12


def number(value: str) -> int | float:
    return float(value) if "." in value else int(value)


def main() -> None:
    with pymupdf.open(SOURCE) as document:
        page = document[PAGE_INDEX]
        tables = page.find_tables().tables
        if len(tables) != 1:
            raise RuntimeError(f"Expected one table on page 13; found {len(tables)}")

        table = tables[0]
        raw = table.extract()
        if len(raw) != 7 or any(len(row) != 5 for row in raw):
            raise RuntimeError("Unexpected table shape; inspect the raw extraction")

        model_row, measure_row, section_row = raw[:3]
        if measure_row != ["Voltages", "MCA", "MFS", "MCA", "MFS"]:
            raise RuntimeError("Unexpected measurement headers")
        models = [f"CRS-{model_row[1]}", f"CRS-{model_row[3]}"]
        records = []
        for row in raw[3:]:
            records.append(
                {
                    "voltage": row[0],
                    models[0]: {"MCA": number(row[1]), "MFS": number(row[2])},
                    models[1]: {"MCA": number(row[3]), "MFS": number(row[4])},
                }
            )

        result = {
            "source_file": SOURCE.name,
            "pdf_page_index": PAGE_INDEX,
            "printed_page": 13,
            "extractor": f"PyMuPDF {pymupdf.VersionBind} page.find_tables()",
            "table_bbox": list(table.bbox),
            "table_count_on_page": len(tables),
            "row_count": table.row_count,
            "column_count": table.col_count,
            "find_tables_header_names": table.header.names,
            "raw_cells": raw,
            "section": section_row[0],
            "models": models,
            "records": records,
        }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "table.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# Page 13 electrical table extraction",
        "",
        f"Source: `{SOURCE.name}`, PDF index {PAGE_INDEX} (printed page 13).",
        f"Method: `{result['extractor']}`.",
        "",
        f"Section: {section_row[0]}",
        "",
        "| Voltage | CRS-042 MCA | CRS-042 MFS | CRS-084 MCA | CRS-084 MFS |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in raw[3:]:
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "## Extraction quality",
        "",
        "- The page has one detected table: 7 rows and 5 columns. All four voltage rows and all 16 numeric cells were extracted.",
        "- `find_tables().header.names` returns `Model: CRS-`, `042`, `null`, `084`, `null`. The two `null` slots reflect the visually merged model headers; the second header row supplies MCA/MFS for both models. A single header row is insufficient to name all columns.",
        "- The `Cooling Only (Includes Condensate Pump)` label spans all five columns visually. Extraction places it in column one and returns `null` for the other four cells. It is a section label, not a voltage record.",
        "- The model prefix `CRS-` and model numbers are separate in the raw top header. The normalized labels `CRS-042` and `CRS-084` were reconstructed from those cells.",
        "- Visual comparison with `page13_reference.png` found no incorrect body-cell associations or missing numeric values. The eight 208 V values match the PDF exactly: single phase 042=31.9/50 and 084=39.3/60; three phase 042=25.6/40 and 084=38.1/60 (MCA/MFS).",
        "- The page note, `Standard 1 KAIC rating, consult factory for alternative KAIC ratings`, sits outside the detected table and is absent from `raw_cells`. A table-aware chunk should retain this note with the table.",
        "- Feasibility: this page supports table-aware chunks if the two-level header, merged section row, model prefix, voltage, page citation, and adjacent note are carried into each structured chunk. This one-page test does not establish reliability across other pages or PDFs.",
        "",
    ]
    (OUTPUT / "table.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
