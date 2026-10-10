# Page 13 electrical table extraction

Source: `STULZ CyberRow DX Engineering Manual QEWR002L.pdf`, PDF index 12 (printed page 13).
Method: `PyMuPDF 1.28.2 page.find_tables()`.

Section: Cooling Only (Includes Condensate Pump)

| Voltage | CRS-042 MCA | CRS-042 MFS | CRS-084 MCA | CRS-084 MFS |
|---|---:|---:|---:|---:|
| 208 V / 1 PH / 60 Hz | 31.9 | 50 | 39.3 | 60 |
| 208 V / 3 PH / 60 Hz | 25.6 | 40 | 38.1 | 60 |
| 460 V / 3 PH / 60 Hz | 12.2 | 15 | 18.8 | 30 |
| 575 V / 3 PH / 60 Hz | 10 | 15 | 13.7 | 20 |

## Extraction quality

- The page has one detected table: 7 rows and 5 columns. All four voltage rows and all 16 numeric cells were extracted.
- `find_tables().header.names` returns `Model: CRS-`, `042`, `null`, `084`, `null`. The two `null` slots reflect the visually merged model headers; the second header row supplies MCA/MFS for both models. A single header row is insufficient to name all columns.
- The `Cooling Only (Includes Condensate Pump)` label spans all five columns visually. Extraction places it in column one and returns `null` for the other four cells. It is a section label, not a voltage record.
- The model prefix `CRS-` and model numbers are separate in the raw top header. The normalized labels `CRS-042` and `CRS-084` were reconstructed from those cells.
- Visual comparison with `page13_reference.png` found no incorrect body-cell associations or missing numeric values. The eight 208 V values match the PDF exactly: single phase 042=31.9/50 and 084=39.3/60; three phase 042=25.6/40 and 084=38.1/60 (MCA/MFS).
- The page note, `Standard 1 KAIC rating, consult factory for alternative KAIC ratings`, sits outside the detected table and is absent from `raw_cells`. A table-aware chunk should retain this note with the table.
- Feasibility: this page supports table-aware chunks if the two-level header, merged section row, model prefix, voltage, page citation, and adjacent note are carried into each structured chunk. This one-page test does not establish reliability across other pages or PDFs.
