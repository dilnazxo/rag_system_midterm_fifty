# Table extraction benchmark

Run: `.venv/Scripts/python.exe results/table_benchmark/benchmark.py` from the repository root.
Method: PyMuPDF 1.28.2 `page.find_tables()`; reference pages rendered at 2x.

## Selection criteria

- Use distinct unsuffixed public engineering manuals; exclude duplicate numbered copies.
- Cover electrical specifications, dimensions, and performance data across at least five manuals.
- Include compact and dense grids, multi-level or merged headers, drawing-adjacent dimension tables, and a table with an adjacent note.
- Use the candidate scan to choose table indexes; this targeted sample tests difficult cases and is not a random corpus estimate or a table-detection recall study.

## Automatic counts

- 15 selected tables from 7 manuals: 5 performance, 7 electrical, 3 dimensions.
- 15 selected candidates returned by `find_tables()`; 0 missing or errored on this run.
- 15 reference page images saved.
- These are output counts for preselected detected candidates, not table-detection recall or correctness scores.

## Human accuracy review

No table has been manually scored. `human_review.csv` provides row/column, header, numeric-cell, and note-preservation fields. Reviewers should compare each raw grid and cell position with its rendered page before filling them.
The JSON includes nearby text blocks as context candidates; their capture has not been assessed as note preservation.

## Selected tables

| ID | Manual | PDF page | Type | Selection reason |
|---|---|---:|---|---|
| cyberrow_dx_p12_performance | STULZ CyberRow DX Engineering Manual QEWR002L.pdf | 12 | performance | Wide cooling-capacity grid with grouped conditions. |
| cyberrow_dx_p13_electrical | STULZ CyberRow DX Engineering Manual QEWR002L.pdf | 13 | electrical | Known merged model headers and a note below the table. |
| cyberrow_cw_p10_performance | STULZ CyberRow CW Engineering Manual QEWR001G.pdf | 10 | performance | Long, multi-column capacity table. |
| cyberrow_cw_p12_electrical | STULZ CyberRow CW Engineering Manual QEWR001G.pdf | 12 | electrical | Compact electrical table with grouped model labels. |
| cyberair_dx_p17_electrical | STULZ CyberAir DX Engineering Manual.pdf | 17 | electrical | Dense 18-column electrical specification table. |
| cyberair_dx_p21_dimensions | STULZ CyberAir DX Engineering Manual.pdf | 21 | dimensions | Small dimension table embedded on a drawing page. |
| cyberone_dx_p24_electrical | STULZ CyberOne DX Engineering Manual.pdf | 24 | electrical | Large model-by-voltage electrical table with grouped columns. |
| cyberone_dx_p27_dimensions | STULZ CyberOne DX Engineering Manual.pdf | 27 | dimensions | Dimension table beside equipment drawings. |
| cyberone_cw_p11_performance | STULZ_CyberOne_CW_Engineering_Manual.pdf | 11 | performance | Capacity table with model and operating-condition headers. |
| cyberone_cw_p19_electrical | STULZ_CyberOne_CW_Engineering_Manual.pdf | 19 | electrical | Dense 10-column power table. |
| heat_rejection_p10_performance | STULZ Heat Rejection Engineering Manual QECS008E.pdf | 10 | performance | Heat-rejection values with nested ambient-condition headers and nearby notes. |
| heat_rejection_p12_dimensions | STULZ Heat Rejection Engineering Manual QECS008E.pdf | 12 | dimensions | Dimensions and weights with grouped model rows. |
| heat_rejection_p18_electrical | STULZ Heat Rejection Engineering Manual QECS008E.pdf | 18 | electrical | Multi-voltage MCA/MFS matrix. |
| glycol_p15_performance | STULZ_Glycol_Systems_Engineering_Manual.pdf | 15 | performance | Dense drycooler capacity table with multi-level headers. |
| glycol_p20_electrical | STULZ_Glycol_Systems_Engineering_Manual.pdf | 20 | electrical | Very wide 19-column drycooler electrical table. |

Each table has a raw Markdown grid in `markdown/`, JSON with cell bounding boxes in `json/`, and a rendered source page in `references/`.
The review CSV is preserved across reruns when selection IDs stay the same.
