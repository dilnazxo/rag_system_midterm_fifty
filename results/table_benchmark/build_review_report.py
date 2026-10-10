"""Build an offline HTML companion for the existing table benchmark exports."""

import csv
import html
import json
import re
from pathlib import Path
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
SELECTION = HERE / "selection.json"
REVIEW_CSV = HERE / "human_review.csv"
OUTPUT = HERE / "review.html"


def escaped(value) -> str:
    return html.escape(str(value), quote=True)


def markdown_cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        raise ValueError(f"Expected a Markdown table row: {line[:80]}")
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line[1:-1])]


def read_markdown_grid(table_id: str) -> list[list[str]]:
    lines = (HERE / "markdown" / f"{table_id}.md").read_text(encoding="utf-8").splitlines()
    table_lines = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            table_lines.append(line)
        elif table_lines:
            break
    if len(table_lines) < 3:
        raise ValueError(f"No extracted Markdown grid for {table_id}")
    rows = [markdown_cells(line) for line in table_lines]
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        raise ValueError(f"Invalid Markdown separator for {table_id}")
    return [rows[0], *rows[2:]]


def render_grid(table_id: str, data: dict) -> str:
    rows = read_markdown_grid(table_id)
    width = data["column_count"]
    if len(rows) != data["row_count"] + 1 or any(len(row) != width for row in rows):
        raise ValueError(f"Markdown and JSON table dimensions differ for {table_id}")
    for row_index, row in enumerate(rows[1:]):
        for column_index, value in enumerate(row):
            expected = (data["raw_grid"][row_index][column_index] or "").replace("\n", "<br>")
            if value != expected:
                raise ValueError(f"Markdown and JSON cell differ for {table_id} at {row_index}, {column_index}")

    parts = ['<table class="extracted-grid"><thead><tr>']
    parts.extend(f"<th scope=\"col\">{escaped(label)}</th>" for label in rows[0])
    parts.append("</tr></thead><tbody>")
    for row_index, row in enumerate(rows[1:]):
        parts.append("<tr>")
        for column_index, value in enumerate(row):
            bbox = data["cells"][row_index][column_index]["bbox"]
            where = f"Row {row_index + 1}, column {column_index + 1}; bbox: {bbox if bbox is not None else 'none'}"
            content = escaped(value).replace("&lt;br&gt;", "<br>")
            parts.append(f'<td title="{escaped(where)}">{content}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def render_case(spec: dict, csv_row_number: int, total: int) -> str:
    table_id = spec["id"]
    data = json.loads((HERE / "json" / f"{table_id}.json").read_text(encoding="utf-8"))
    if data["filename"] != spec["filename"] or data["pdf_page_index"] != spec["page_index"]:
        raise ValueError(f"Selection and JSON source differ for {table_id}")
    image_path = HERE / data["reference_image"]
    if not image_path.is_file():
        raise FileNotFoundError(image_path)
    image_url = quote(data["reference_image"], safe="/._-")
    markdown_url = quote(f"markdown/{table_id}.md", safe="/._-")
    json_url = quote(f"json/{table_id}.json", safe="/._-")
    pdf_url = quote(f"../../data/manuals/{spec['filename']}", safe="/._-") + f"#page={spec['page_index'] + 1}"
    context = data.get("nearby_text_blocks", [])
    context_html = "".join(
        f"<li><pre>{escaped(block['text'])}</pre></li>" for block in context
    ) or "<li>No nearby text blocks captured.</li>"
    header_html = escaped(json.dumps(data.get("raw_header", {}).get("names"), ensure_ascii=False))
    grid = render_grid(table_id, data) if data["detection_success"] else f"<p>Detection failed: {escaped(data.get('error', 'unknown error'))}</p>"
    return f"""
    <section class="case" id="{escaped(table_id)}" data-table-id="{escaped(table_id)}">
      <div class="case-head">
        <div><span class="case-number">{csv_row_number - 1:02d} / {total}</span>
          <h2>{escaped(table_id)}</h2>
          <p class="meta"><strong>{escaped(spec['filename'])}</strong> · PDF page {spec['page_index'] + 1} · {escaped(spec['category'])}</p>
          <p class="reason">{escaped(spec['reason'])}</p></div>
        <div class="links"><a href="{image_url}" target="_blank">Full-size page</a>
          <a href="{pdf_url}" target="_blank">Source PDF</a>
          <a href="{markdown_url}" target="_blank">Markdown</a>
          <a href="{json_url}" target="_blank">JSON + positions</a>
          <span>CSV row {csv_row_number}</span></div>
      </div>
      <div class="comparison">
        <figure class="page-pane"><figcaption>Rendered PDF page</figcaption>
          <a href="{image_url}" target="_blank"><img src="{image_url}" alt="Rendered PDF page {spec['page_index'] + 1} from {escaped(spec['filename'])}" loading="lazy"></a>
        </figure>
        <div class="table-pane"><h3>Extracted Markdown table</h3>
          <p class="hint">Column labels are positional. Hover over a cell for its extracted bounding box.</p>
          <div class="grid-scroll">{grid}</div>
          <p class="raw-header">Raw <code>find_tables()</code> header names: <code>{header_html}</code></p>
          <details><summary>Nearby text candidates ({len(context)}; unverified)</summary>
            <ul class="context-list">{context_html}</ul>
          </details>
        </div>
      </div>
      <p class="record">Record findings in <a href="human_review.csv">human_review.csv</a>, row {csv_row_number}, using table ID <code>{escaped(table_id)}</code>. Leave uncertain fields blank and explain the issue in <code>reviewer_notes</code>.</p>
    </section>"""


def main() -> None:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))["tables"]
    with REVIEW_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        review_rows = list(csv.DictReader(stream))
    if [row["table_id"] for row in review_rows] != [spec["id"] for spec in selection]:
        raise ValueError("Review CSV rows and selection order differ")

    navigation = "".join(
        f'<a href="#{escaped(spec["id"])}"><span>{index:02d}</span> {escaped(spec["category"])} · {escaped(spec["id"])}</a>'
        for index, spec in enumerate(selection, start=1)
    )
    cases = "\n".join(render_case(spec, index + 1, len(selection)) for index, spec in enumerate(selection, start=1))
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Table extraction · human review</title>
<style>
  :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #172339; background: #f4f6f9; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; }}
  a {{ color: #0755a0; }}
  .masthead {{ background: #102640; color: #fff; padding: 2rem max(1.5rem, calc((100vw - 1500px)/2)); }}
  .masthead h1 {{ margin: 0 0 .3rem; font-size: clamp(1.7rem, 3vw, 2.5rem); }}
  .masthead p {{ margin: .4rem 0; color: #dce7f2; }}
  .masthead a {{ color: #badeff; }}
  main {{ max-width: 1500px; margin: auto; padding: 1.2rem; }}
  .intro, .case {{ background: #fff; border: 1px solid #d9e1ea; border-radius: 12px; box-shadow: 0 2px 10px #15243a0b; }}
  .intro {{ padding: 1.3rem 1.6rem; }}
  .intro h2 {{ margin-top: 0; }}
  .intro li {{ margin: .45rem 0; }}
  .index {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); gap: .5rem; margin: 1rem 0 2rem; }}
  .index a {{ display: block; padding: .65rem .8rem; background: #fff; border: 1px solid #d9e1ea; border-radius: 8px; text-decoration: none; overflow-wrap: anywhere; }}
  .index a:hover, .index a:focus {{ background: #e8f2ff; }}
  .index span {{ color: #536b84; font-variant-numeric: tabular-nums; }}
  .case {{ margin: 0 0 2rem; padding: 1.2rem; scroll-margin-top: 1rem; }}
  .case-head {{ display: flex; justify-content: space-between; gap: 1rem; align-items: start; border-bottom: 1px solid #d9e1ea; padding-bottom: .8rem; }}
  .case-number {{ color: #5c7188; font-size: .85rem; letter-spacing: .08em; }}
  .case h2 {{ margin: .2rem 0; overflow-wrap: anywhere; }}
  .meta, .reason {{ margin: .35rem 0; }}
  .meta {{ color: #3d5269; }}
  .links {{ display: flex; flex-wrap: wrap; gap: .4rem; justify-content: end; max-width: 420px; }}
  .links a, .links span {{ border: 1px solid #cbd8e5; border-radius: 6px; padding: .35rem .5rem; white-space: nowrap; font-size: .9rem; }}
  .links span {{ background: #eef3f8; }}
  .comparison {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 1rem; margin-top: 1rem; align-items: start; }}
  .page-pane, .table-pane {{ min-width: 0; margin: 0; }}
  .page-pane {{ border: 1px solid #d7dee7; background: #f7f9fb; text-align: center; }}
  .page-pane figcaption {{ font-weight: 700; padding: .6rem; text-align: left; }}
  .page-pane img {{ display: block; width: 100%; height: auto; }}
  .table-pane h3 {{ margin: .3rem 0 .25rem; }}
  .hint {{ margin: .2rem 0 .7rem; font-size: .9rem; color: #556a80; }}
  .grid-scroll {{ max-height: 78vh; overflow: auto; border: 1px solid #c9d4df; }}
  .extracted-grid {{ border-collapse: collapse; font-size: .84rem; min-width: 100%; }}
  .extracted-grid th, .extracted-grid td {{ border: 1px solid #d3dce5; padding: .34rem .42rem; text-align: left; vertical-align: top; min-width: 62px; }}
  .extracted-grid th {{ position: sticky; top: 0; z-index: 1; background: #e7eff9; white-space: nowrap; }}
  .extracted-grid tbody tr:nth-child(even) {{ background: #f7f9fc; }}
  .extracted-grid td:hover {{ background: #fff2c6; }}
  .raw-header {{ overflow-wrap: anywhere; line-height: 1.5; }}
  code {{ background: #eef2f6; padding: .1rem .25rem; border-radius: 3px; }}
  details {{ border-top: 1px solid #e0e6ed; padding-top: .5rem; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  .context-list {{ padding-left: 1.2rem; }}
  .context-list pre {{ white-space: pre-wrap; font: inherit; margin: .4rem 0; }}
  .record {{ border-top: 1px solid #d9e1ea; padding-top: .8rem; margin-bottom: 0; }}
  @media (max-width: 850px) {{ .comparison {{ grid-template-columns: 1fr; }} .case-head {{ flex-direction: column; }} .links {{ justify-content: start; max-width: none; }} }}
</style></head><body>
<header class="masthead"><h1>Table extraction · human review</h1>
<p>{len(selection)} selected tables · {len({spec['filename'] for spec in selection})} manuals · offline comparison report</p>
<p>Compare each rendered page with the raw extracted grid. This report contains no accuracy judgments.</p></header>
<main><section class="intro"><h2>Review each table</h2>
<ol>
  <li><strong>Rows and columns:</strong> check the table boundary, row count, column count, missing or extra rows, and merged cells.</li>
  <li><strong>Headers:</strong> check model names, voltage or condition groups, subheaders, units, and header spans against the page.</li>
  <li><strong>Numerical cells:</strong> compare values exactly, including decimals, signs, units, and unavailable-value markers.</li>
  <li><strong>Cell associations:</strong> verify every value is attached to the correct model, voltage, operating condition, and measurement.</li>
  <li><strong>Notes:</strong> inspect footnotes and nearby text on the page. The JSON lists nearby text candidates, but their capture is unverified.</li>
</ol>
<p>Enter findings in <a href="human_review.csv">human_review.csv</a> using the table ID and CSV row shown on each card. Keep uncertain accuracy fields blank and explain uncertainty in <code>reviewer_notes</code>. Open the page image for full-size inspection. No scores have been calculated.</p>
</section><nav class="index" aria-label="Table index">{navigation}</nav>
{cases}
</main></body></html>
"""
    OUTPUT.write_text(document, encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(selection)} table comparisons")


if __name__ == "__main__":
    main()
