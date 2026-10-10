"""Experimental reconstruction of two benchmark performance-table layouts.

Reads saved PyMuPDF benchmark JSON only. It does not alter PDF extraction or RAG code.
"""

import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "reconstructed"
DEFAULT_TABLE_IDS = (
    "cyberrow_cw_p10_performance",
    "cyberrow_dx_p12_performance",
)
AIR_RE = re.compile(
    r"(?P<db>\d+(?:\.\d+)?)\s*°F\s*DB\s*/\s*(?P<wb>\d+(?:\.\d+)?)\s*°F\s*WB",
    re.IGNORECASE,
)
EWT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*°F\s*EWT", re.IGNORECASE)
DELTA_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*°F\s*ΔT", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")


def flag(flags: list[dict], code: str, message: str, row: int | None = None, column: int | None = None) -> None:
    item = {"code": code, "message": message}
    if row is not None:
        item["row"] = row
    if column is not None:
        item["column"] = column
    if item not in flags:
        flags.append(item)


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_number(raw: str | None):
    if not nonempty(raw) or not NUMBER_RE.fullmatch(raw.strip()):
        return None
    clean = raw.replace(",", "")
    return float(clean) if "." in clean else int(clean)


def condition_from_section(section: dict) -> dict:
    match = AIR_RE.search(section["text"])
    return {
        "entering_air_temperature_raw": section["text"],
        "dry_bulb_F": float(match["db"]) if match else None,
        "wet_bulb_F": float(match["wb"]) if match else None,
        "source_row": section["row"],
        "source_bbox": section["bbox"],
    }


def detect_full_width_sections(data: dict) -> list[dict]:
    """Require a true full-width cell and a nearby dense body row."""
    grid, cells = data["raw_grid"], data["cells"]
    left, right = data["table_bbox"][0], data["table_bbox"][2]
    width = right - left
    sections = []
    for row_index, row in enumerate(grid):
        populated = [column for column, value in enumerate(row) if nonempty(value)]
        if populated != [0]:
            continue
        first_bbox = cells[row_index][0]["bbox"]
        if first_bbox is None or width <= 0:
            continue
        span_ratio = (first_bbox[2] - first_bbox[0]) / width
        aligned = abs(first_bbox[0] - left) <= 2 and abs(first_bbox[2] - right) <= 2
        empty_slots_have_no_boxes = all(cell["bbox"] is None for cell in cells[row_index][1:])
        next_data_row = next(
            (
                later
                for later in range(row_index + 1, min(row_index + 4, len(grid)))
                if sum(nonempty(value) for value in grid[later]) >= max(3, len(row) // 2)
            ),
            None,
        )
        if span_ratio < 0.95 or not aligned or not empty_slots_have_no_boxes or next_data_row is None:
            continue
        label = row[0].strip()
        if "Entering Air Temperature" in label:
            kind = "entering_air_temperature"
        elif "Net DX Cooling Capacity" in label:
            kind = "measurement_scope"
        elif "Cooling Only" in label:
            kind = "operating_mode"
        else:
            kind = "unknown_full_width"
        sections.append(
            {
                "row": row_index,
                "text": row[0],
                "kind": kind,
                "colspan": len(row),
                "bbox": first_bbox,
                "evidence": {
                    "nonempty_columns": populated,
                    "span_ratio": round(span_ratio, 5),
                    "aligned_with_table_edges": aligned,
                    "empty_slots_have_no_boxes": empty_slots_have_no_boxes,
                    "next_dense_row": next_data_row,
                },
            }
        )
    return sections


def unit_from_raw(raw: str | None) -> tuple[str | None, str]:
    if not nonempty(raw):
        return None, "missing"
    compact = " ".join(raw.split())
    if compact in ("Btu/h", "kW", "GPM", "MBH"):
        return compact, "direct"
    if re.fullmatch(r"ftH\s*0\s*2", compact, re.IGNORECASE):
        return "ftH2O", "needs_review"
    return compact, "needs_review"


def dense_column_cells(data: dict) -> list[dict]:
    for row in data["cells"]:
        if sum(cell["bbox"] is not None for cell in row) == data["column_count"]:
            return row
    raise ValueError("No fully boxed row for column geometry")


def cw_column_headers(data: dict, flags: list[dict]) -> list[dict]:
    """Associate merged top headers with leaf columns by bounding-box overlap."""
    top = data["cells"][0]
    units = data["cells"][1]
    leaf_cells = dense_column_cells(data)
    headers = []
    for column, leaf in enumerate(leaf_cells):
        bbox = leaf["bbox"]
        center = (bbox[0] + bbox[2]) / 2
        parents = [
            cell for cell in top
            if nonempty(cell["text"]) and cell["bbox"] is not None
            and cell["bbox"][0] - 1 <= center <= cell["bbox"][2] + 1
        ]
        parent = parents[0] if len(parents) == 1 else None
        raw_parent = parent["text"] if parent else None
        raw_unit = units[column]["text"]
        unit, unit_status = unit_from_raw(raw_unit)
        status = "geometry_and_text" if parent and (column < 2 or unit_status == "direct") else "needs_review"
        if column < 2:
            role = "EWT" if column == 0 else "delta_T"
            status = "inferred_from_data_pattern"
        else:
            role = "measurement"
        if status != "geometry_and_text":
            flag(
                flags,
                "header_association_needs_review",
                f"Column {column + 1}: parent={raw_parent!r}, raw unit={raw_unit!r}; association={status}",
                row=0,
                column=column,
            )
        headers.append(
            {
                "column": column,
                "role": role,
                "parent_header_raw": raw_parent,
                "parent_header_bbox": parent["bbox"] if parent else None,
                "unit_raw": raw_unit,
                "unit": unit,
                "unit_status": unit_status,
                "association_status": status,
            }
        )
    return headers


def measure(data: dict, row: int, column: int, name: str, unit: str | None,
            raw_unit: str | None, association_status: str, flags: list[dict]) -> dict:
    cell = data["cells"][row][column]
    value = parse_number(cell["text"])
    if nonempty(cell["text"]) and value is None:
        flag(flags, "numeric_value_unparsed", f"Unparsed raw value {cell['text']!r}", row, column)
    return {
        "name": name,
        "unit": unit,
        "unit_raw": raw_unit,
        "raw_value": cell["text"],
        "value": value,
        "header_association": association_status,
        "source_cell": cell,
    }


def base_result(data: dict, layout: str) -> dict:
    return {
        "table_id": data["table_id"],
        "source_file": data["filename"],
        "page": data["pdf_page_number"],
        "pdf_page_index": data["pdf_page_index"],
        "layout": layout,
        "raw_extraction": data,
        "full_width_sections": detect_full_width_sections(data),
        "column_headers": [],
        "records": [],
        "review_flags": [],
        "automatic_reconstruction_only": True,
    }


def reconstruct_cw(data: dict) -> dict:
    result = base_result(data, "capacity_by_ewt_and_delta_t")
    flags = result["review_flags"]
    headers = cw_column_headers(data, flags)
    result["column_headers"] = headers
    cabinet = data["raw_grid"][0][0]
    nearby = "\n".join(block["text"] for block in data.get("nearby_text_blocks", []))
    model_match = re.search(r"\bModel\s+(CRS-[A-Z0-9-]+)", nearby)
    model = model_match.group(1) if model_match else None
    if model is None:
        flag(flags, "equipment_missing", "Model name was not found in nearby text")
    else:
        flag(flags, "equipment_from_nearby_text", "Model was read from text outside the table; confirm against the page")
    equipment = {"model": model, "cabinet": cabinet}
    result["equipment_context"] = equipment
    by_row = {section["row"]: section for section in result["full_width_sections"]}
    condition = None
    ewt = None
    for row_index in range(2, data["row_count"]):
        section = by_row.get(row_index)
        if section:
            if section["kind"] == "entering_air_temperature":
                condition = condition_from_section(section)
                ewt = None  # A new air-temperature section starts a new EWT group.
            continue
        row = data["raw_grid"][row_index]
        if not nonempty(row[1]) or sum(nonempty(value) for value in row[2:]) < 2:
            continue
        if condition is None:
            flag(flags, "condition_missing", "Data row has no preceding air-temperature section", row_index)
        if nonempty(row[0]):
            match = EWT_RE.fullmatch(row[0].strip())
            ewt = {
                "raw": row[0], "value": float(match["value"]) if match else None,
                "unit": "°F", "source_row": row_index, "forward_filled": False,
            }
            if match is None:
                flag(flags, "ewt_unparsed", f"Could not parse EWT {row[0]!r}", row_index, 0)
        elif ewt is not None:
            ewt = {**ewt, "forward_filled": True}
        else:
            flag(flags, "ewt_missing_after_section", "Blank EWT at start of a new section was not filled", row_index, 0)
        delta_match = DELTA_RE.fullmatch(row[1].strip())
        delta_t = {
            "raw": row[1], "value": float(delta_match["value"]) if delta_match else None,
            "unit": "°F", "source_row": row_index,
        }
        if delta_match is None:
            flag(flags, "delta_t_unparsed", f"Could not parse delta_T {row[1]!r}", row_index, 1)
        measurements = [
            measure(
                data, row_index, column,
                " ".join((header["parent_header_raw"] or "Unknown measurement").split()),
                header["unit"], header["unit_raw"], header["association_status"], flags,
            )
            for column, header in enumerate(headers) if column >= 2
        ]
        result["records"].append(
            {
                "equipment": equipment,
                "operating_conditions": condition,
                "EWT": ewt,
                "delta_T": delta_t,
                "measurements": measurements,
                "source_file": data["filename"],
                "page": data["pdf_page_number"],
                "table_id": data["table_id"],
                "source_row": row_index,
            }
        )
    return result


def reconstruct_dx(data: dict) -> dict:
    result = base_result(data, "capacity_by_model_and_air_temperature")
    flags = result["review_flags"]
    prefix_raw = data["raw_grid"][0][0]
    prefix_match = re.search(r"Model:\s*([A-Z]+-)", prefix_raw or "")
    prefix = prefix_match.group(1) if prefix_match else ""
    if not prefix:
        flag(flags, "model_prefix_missing", f"Could not parse model prefix {prefix_raw!r}", 0, 0)
    model_headers = []
    for column in range(2, data["column_count"]):
        raw = data["raw_grid"][0][column]
        model = prefix + re.sub(r"\s*-\s*", "-", raw or "")
        model_headers.append({"column": column, "model_raw": raw, "prefix_raw": prefix_raw, "model": model,
                              "source_cell": data["cells"][0][column], "association_status": "needs_review"})
    result["column_headers"] = model_headers
    flag(flags, "model_prefix_joined", "Model names join a shared prefix and per-column suffix; confirm spacing", 0)
    by_row = {section["row"]: section for section in result["full_width_sections"]}
    condition = None
    scope = None
    unit = None
    current_records = {}

    def flush_records():
        result["records"].extend(current_records.values())
        current_records.clear()

    for row_index in range(1, data["row_count"]):
        section = by_row.get(row_index)
        if section:
            if section["kind"] == "measurement_scope":
                scope = section["text"]
            elif section["kind"] == "entering_air_temperature":
                flush_records()
                condition = condition_from_section(section)
                unit = None  # Unit row spans cannot cross a section boundary.
            continue
        row = data["raw_grid"][row_index]
        if row[0] not in ("Total", "Sensible") or sum(nonempty(value) for value in row[2:]) < 2:
            continue
        if nonempty(row[1]):
            unit = row[1].strip()
        elif unit is None:
            flag(flags, "unit_missing_after_section", "Blank unit was not filled across a section boundary", row_index, 1)
        if condition is None:
            flag(flags, "condition_missing", "Data row has no preceding air-temperature section", row_index)
        for header in model_headers:
            column = header["column"]
            model = header["model"]
            if model not in current_records:
                current_records[model] = {
                    "equipment": {"model": model, "model_raw": header["model_raw"], "cabinet": None},
                    "operating_conditions": condition,
                    "EWT": None,
                    "delta_T": None,
                    "measurement_scope": scope,
                    "measurements": [],
                    "source_file": data["filename"],
                    "page": data["pdf_page_number"],
                    "table_id": data["table_id"],
                }
            current_records[model]["measurements"].append(
                measure(
                    data, row_index, column, f"Net DX Cooling Capacity - {row[0]}",
                    unit, row[1], "model_column_and_grouped_unit", flags,
                )
            )
    flush_records()
    return result


def reconstruct(data: dict) -> dict:
    if data["column_count"] == 8 and "in Cabinet" in (data["raw_grid"][0][0] or ""):
        return reconstruct_cw(data)
    if data["column_count"] == 8 and (data["raw_grid"][0][0] or "").startswith("Model: CRS-"):
        return reconstruct_dx(data)
    raise ValueError(f"Unsupported table layout: {data['table_id']}")


def markdown_value(value) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>")


def reconstructed_markdown(result: dict) -> str:
    lines = [
        f"# Reconstructed table: {result['table_id']}", "",
        f"Source: `{result['source_file']}`, PDF page {result['page']}.",
        "Automatic structure reconstruction only; check the source page before treating associations as correct.",
        f"Raw source: [`{result['table_id']}.json`](../json/{result['table_id']}.json).", "",
        "## Full-width sections", "",
        "| Source row | Kind | Reconstructed colspan | Raw label |",
        "|---:|---|---:|---|",
    ]
    for section in result["full_width_sections"]:
        lines.append(f"| {section['row']} | {section['kind']} | {section['colspan']} | {markdown_value(section['text'])} |")
    lines += ["", "## Column headers", ""]
    if result["layout"] == "capacity_by_ewt_and_delta_t":
        lines += ["| Column | Role | Merged parent header | Raw unit | Unit | Association |",
                  "|---:|---|---|---|---|---|"]
        for header in result["column_headers"]:
            lines.append("| " + " | ".join(markdown_value(header[key]) for key in
                ("column", "role", "parent_header_raw", "unit_raw", "unit", "association_status")) + " |")
        lines += ["", "## Reconstructed data", ""]
        groups = {}
        for record in result["records"]:
            label = record["operating_conditions"]["entering_air_temperature_raw"] if record["operating_conditions"] else "Unknown condition"
            groups.setdefault(label, []).append(record)
        for label, records in groups.items():
            lines += [f"### {label}", "",
                      f"Equipment: {records[0]['equipment']['model']}; {records[0]['equipment']['cabinet']}.", "",
                      "| EWT | ΔT | Net Total (Btu/h) | Net Total (kW) | Net Sensible (Btu/h) | Net Sensible (kW) | Flow Rate (GPM) | Pressure Drop (ftH2O*) |",
                      "|---|---|---:|---:|---:|---:|---:|---:|"]
            for record in records:
                values = [record["EWT"]["raw"] if record["EWT"] else "", record["delta_T"]["raw"]]
                values += [measurement["raw_value"] for measurement in record["measurements"]]
                lines.append("| " + " | ".join(markdown_value(value) for value in values) + " |")
            lines.append("")
        lines += ["*Pressure-drop unit normalized from the raw extracted text; manual review required.*", ""]
    else:
        lines += ["| Column | Raw model header | Joined model | Association |",
                  "|---:|---|---|---|"]
        for header in result["column_headers"]:
            lines.append("| " + " | ".join(markdown_value(header[key]) for key in
                ("column", "model_raw", "model", "association_status")) + " |")
        lines += ["", "## Reconstructed data", ""]
        groups = {}
        for record in result["records"]:
            label = record["operating_conditions"]["entering_air_temperature_raw"] if record["operating_conditions"] else "Unknown condition"
            groups.setdefault(label, []).append(record)
        for label, records in groups.items():
            lines += [f"### {label}", "", "| Model | Total MBH | Sensible MBH | Total kW | Sensible kW |",
                      "|---|---:|---:|---:|---:|"]
            for record in records:
                values = [record["equipment"]["model"]] + [measurement["raw_value"] for measurement in record["measurements"]]
                lines.append("| " + " | ".join(markdown_value(value) for value in values) + " |")
            lines.append("")
    lines += ["## Manual-review flags", ""]
    lines += [f"- `{item['code']}`: {item['message']}" for item in result["review_flags"]]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for table_id in DEFAULT_TABLE_IDS:
        source = json.loads((HERE / "json" / f"{table_id}.json").read_text(encoding="utf-8"))
        result = reconstruct(source)
        (OUTPUT / f"{table_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (OUTPUT / f"{table_id}.md").write_text(reconstructed_markdown(result), encoding="utf-8")
        summary.append({"table_id": table_id, "records": len(result["records"]),
                        "full_width_sections": len(result["full_width_sections"]),
                        "review_flags": len(result["review_flags"])})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
