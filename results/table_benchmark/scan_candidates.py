"""List table candidates in distinct, unsuffixed public engineering manuals."""

from pathlib import Path
import sys

import pymupdf


MANUALS = [
    "STULZ CyberRow DX Engineering Manual QEWR002L.pdf",
    "STULZ CyberRow CW Engineering Manual QEWR001G.pdf",
    "STULZ CyberAir DX Engineering Manual.pdf",
    "STULZ CyberOne DX Engineering Manual.pdf",
    "STULZ_CyberOne_CW_Engineering_Manual.pdf",
    "STULZ Heat Rejection Engineering Manual QECS008E.pdf",
    "STULZ_Glycol_Systems_Engineering_Manual.pdf",
]
PDF_DIR = Path(__file__).resolve().parents[2] / "data/manuals"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for name in MANUALS:
        print(f"\n### {name}", flush=True)
        with pymupdf.open(PDF_DIR / name) as doc:
            for page_index, page in enumerate(doc):
                tables = page.find_tables().tables
                if not tables:
                    continue
                lines = [s.strip() for s in page.get_text("text").splitlines() if s.strip()]
                heading = " | ".join(lines[:5]).replace("\t", " ")[:120]
                for table_index, table in enumerate(tables):
                    raw = table.extract()
                    preview = " / ".join(
                        str(cell).replace("\n", " ")[:35]
                        for row in raw[:2]
                        for cell in row[:3]
                        if cell
                    )[:140]
                    print(
                        f"p{page_index + 1} t{table_index} {table.row_count}x{table.col_count} "
                        f"head={heading!r} preview={preview!r}",
                        flush=True,
                    )


if __name__ == "__main__":
    main()
