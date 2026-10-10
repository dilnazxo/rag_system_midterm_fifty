"""Re-run a fixed, reviewable PyMuPDF table-extraction sample."""

import csv
import json
from collections import Counter
from pathlib import Path

import pymupdf


HERE = Path(__file__).resolve().parent
PDF_DIR = HERE.parents[1] / "data/manuals"
MANIFEST = HERE / "selection.json"
REVIEW_COLUMNS = [
    "table_id",
    "filename",
    "pdf_page_index",
    "pdf_page_number",
    "category",
    "detection_success",
    "row_column_accuracy",
    "header_accuracy",
    "numeric_cell_accuracy",
    "notes_preserved",
    "reviewer_notes",
]


def rect_list(rect) -> list[float] | None:
    return list(rect) if rect is not None else None


def markdown_cell(value: str | None) -> str:
    return (value or "").replace("|", "\\|").replace("\n", "<br>")


def nearby_blocks(page, table_bbox, max_distance=72):
    """Capture possible context outside the grid; this is not note validation."""
    table_rect = pymupdf.Rect(table_bbox)
    blocks = []
    for block in page.get_text("blocks"):
        if len(block) < 5 or not isinstance(block[4], str):
            continue
        rect = pymupdf.Rect(block[:4])
        if rect.intersects(table_rect):
            continue
        vertical_gap = max(table_rect.y0 - rect.y1, rect.y0 - table_rect.y1, 0)
        horizontal_overlap = min(rect.x1, table_rect.x1) > max(rect.x0, table_rect.x0)
        if horizontal_overlap and vertical_gap <= max_distance:
            text = block[4].strip()
            if text:
                blocks.append({"bbox": rect_list(rect), "text": text})
    return blocks


def export_one(spec, document):
    page = document[spec["page_index"]]
    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(
        HERE / "references" / f"{spec['id']}.png"
    )
    result = {
        "table_id": spec["id"],
        "filename": spec["filename"],
        "pdf_page_index": spec["page_index"],
        "pdf_page_number": spec["page_index"] + 1,
        "table_index": spec["table_index"],
        "category": spec["category"],
        "selection_reason": spec["reason"],
        "extractor": f"PyMuPDF {pymupdf.VersionBind} page.find_tables()",
        "reference_image": f"references/{spec['id']}.png",
    }
    try:
        tables = page.find_tables().tables
        result["tables_found_on_page"] = len(tables)
        if spec["table_index"] >= len(tables):
            raise LookupError("Selected table index was not returned by find_tables()")
        table = tables[spec["table_index"]]
        raw_grid = table.extract()
        cell_rows = []
        for row_index, row in enumerate(raw_grid):
            cell_rows.append(
                [
                    {
                        "row": row_index,
                        "column": column_index,
                        "text": value,
                        "bbox": rect_list(table.rows[row_index].cells[column_index]),
                    }
                    for column_index, value in enumerate(row)
                ]
            )
        result.update(
            {
                "detection_success": True,
                "table_bbox": rect_list(table.bbox),
                "row_count": table.row_count,
                "column_count": table.col_count,
                "raw_header": {
                    "names": table.header.names,
                    "bbox": rect_list(table.header.bbox),
                    "external": table.header.external,
                },
                "raw_grid": raw_grid,
                "cells": cell_rows,
                "nearby_text_blocks": nearby_blocks(page, table.bbox),
            }
        )
    except Exception as exc:
        result.update({"detection_success": False, "error": str(exc)})

    (HERE / "json" / f"{spec['id']}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        f"# {spec['id']}",
        "",
        f"Source: `{spec['filename']}`, PDF index {spec['page_index']} (PDF page {spec['page_index'] + 1}), table index {spec['table_index']}.",
        f"Category: {spec['category']}. Selection reason: {spec['reason']}",
        f"Reference image: [`{spec['id']}.png`](../references/{spec['id']}.png).",
        "",
        "Raw extraction follows; column labels are positional and have not been interpreted or verified.",
        "",
    ]
    if result["detection_success"]:
        labels = [f"Column {i + 1}" for i in range(table.col_count)]
        lines += [
            "| " + " | ".join(labels) + " |",
            "| " + " | ".join("---" for _ in labels) + " |",
        ]
        for row in raw_grid:
            lines.append("| " + " | ".join(markdown_cell(v) for v in row) + " |")
        lines += [
            "",
            "Raw header names: `" + json.dumps(table.header.names, ensure_ascii=False) + "`.",
            "Cell bounding boxes and nearby text blocks are in the JSON export.",
        ]
    else:
        lines.append(f"Detection failed: {result['error']}")
    (HERE / "markdown" / f"{spec['id']}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return result


def write_review_csv(results):
    review_path = HERE / "human_review.csv"
    previous = {}
    if review_path.exists():
        with review_path.open("r", encoding="utf-8-sig", newline="") as stream:
            previous = {row["table_id"]: row for row in csv.DictReader(stream)}
    if previous and set(previous) != {item["table_id"] for item in results}:
        raise ValueError("Review CSV table IDs differ from the selection; preserve annotations before changing it")
    with review_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        written_rows = []
        for item in results:
            row = {field: "" for field in REVIEW_COLUMNS}
            row.update({key: value for key, value in previous.get(item["table_id"], {}).items() if key in REVIEW_COLUMNS})
            row.update(
                {
                    "table_id": item["table_id"],
                    "filename": item["filename"],
                    "pdf_page_index": item["pdf_page_index"],
                    "pdf_page_number": item["pdf_page_number"],
                    "category": item["category"],
                    "detection_success": str(item["detection_success"]).lower(),
                }
            )
            writer.writerow(row)
            written_rows.append(row)
    return written_rows


def main():
    selection = json.loads(MANIFEST.read_text(encoding="utf-8"))
    specs = selection["tables"]
    if len(specs) != len({spec["id"] for spec in specs}):
        raise ValueError("Selection IDs must be unique")
    for subdir in ("json", "markdown", "references"):
        (HERE / subdir).mkdir(parents=True, exist_ok=True)

    results = []
    for filename in dict.fromkeys(spec["filename"] for spec in specs):
        with pymupdf.open(PDF_DIR / filename) as document:
            results.extend(export_one(spec, document) for spec in specs if spec["filename"] == filename)
    review_rows = write_review_csv(results)

    counts = {
        "selected_tables": len(results),
        "distinct_manuals": len({item["filename"] for item in results}),
        "by_category": dict(Counter(item["category"] for item in results)),
        "selected_candidates_returned_by_find_tables": sum(item["detection_success"] for item in results),
        "selected_candidates_missing_or_error": sum(not item["detection_success"] for item in results),
        "rendered_reference_pages": len(results),
    }
    (HERE / "automatic_summary.json").write_text(
        json.dumps(counts, indent=2) + "\n", encoding="utf-8"
    )
    manual_fields = REVIEW_COLUMNS[6:]
    reviewed_rows = sum(
        any((row[field] or "").strip() for field in manual_fields)
        for row in review_rows
    )
    (HERE / "human_review_status.json").write_text(
        json.dumps(
            {
                "rows_with_any_manual_review_entry": reviewed_rows,
                "accuracy_aggregates": None,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Table extraction benchmark",
        "",
        "Run: `.venv/Scripts/python.exe results/table_benchmark/benchmark.py` from the repository root.",
        f"Method: PyMuPDF {pymupdf.VersionBind} `page.find_tables()`; reference pages rendered at 2x.",
        "",
        "## Selection criteria",
        "",
        *[f"- {criterion}" for criterion in selection["selection_criteria"]],
        "",
        "## Automatic counts",
        "",
        f"- {counts['selected_tables']} selected tables from {counts['distinct_manuals']} manuals: "
        + ", ".join(f"{count} {category}" for category, count in counts["by_category"].items()) + ".",
        f"- {counts['selected_candidates_returned_by_find_tables']} selected candidates returned by `find_tables()`; "
        f"{counts['selected_candidates_missing_or_error']} missing or errored on this run.",
        f"- {counts['rendered_reference_pages']} reference page images saved.",
        "- These are output counts for preselected detected candidates, not table-detection recall or correctness scores.",
        "",
        "## Human accuracy review",
        "",
        ("No table has been manually scored. " if reviewed_rows == 0 else f"{reviewed_rows} rows contain human-entered review fields. ")
        + "`human_review.csv` provides row/column, header, numeric-cell, and note-preservation fields. Reviewers should compare each raw grid and cell position with its rendered page before filling them.",
        "The JSON includes nearby text blocks as context candidates; their capture has not been assessed as note preservation.",
        "",
        "## Selected tables",
        "",
        "| ID | Manual | PDF page | Type | Selection reason |",
        "|---|---|---:|---|---|",
    ]
    for spec in specs:
        lines.append(
            f"| {spec['id']} | {spec['filename']} | {spec['page_index'] + 1} | "
            f"{spec['category']} | {spec['reason']} |"
        )
    lines += [
        "",
        "Each table has a raw Markdown grid in `markdown/`, JSON with cell bounding boxes in `json/`, and a rendered source page in `references/`.",
        "The review CSV is preserved across reruns when selection IDs stay the same.",
        "",
    ]
    (HERE / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
