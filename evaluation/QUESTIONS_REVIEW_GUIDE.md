# Stage 5.2 candidate question review

`questions_candidates.csv` contains 30 **unverified candidates**. It uses exactly the schema and label conventions in [README.md](README.md). The page numbers are one-based **PDF page indices**, which differ from printed page numbers in some manuals. The proposed document, page, and chunk labels are review aids, not ground truth. Every `verified` value remains `false`. `questions.csv` remains the empty Stage 5.1 template.

## How to review each row

1. Open the exact PDF in `data/manuals/` and inspect the listed page visually. Confirm the question's equipment, operating condition, units, row, column, and proposed answer. Check whether another page or manual also answers it.
2. Independently inspect each proposed ID in `data/index/chunks.json`. A correct document or page label does **not** make a chunk label correct. Check whether the chunk contains enough of the question's facts to be relevant and whether important supporting chunks are missing.
3. Correct or remove any uncertain document, page, or chunk labels. For no-answer candidates, search the full indexed corpus and visually check likely manuals before accepting the absence claim.
4. Only then set `verified=true` in a reviewed copy or transfer a reviewed row into `questions.csv`. Leave `verified=false` if any label is unresolved. The evaluation runner excludes these candidates until that step.

The following are **candidate PDF cues to inspect**, not scored answers or verified ground truth. They make it possible to review every question without searching from scratch.

| IDs | PDF and pages | Evidence to check |
|---|---|---|
| q001–q002, q011 | `STULZ CyberRow DX Engineering Manual QEWR002L.pdf`, p13 | Cooling-only electrical table; CRS-042 and CRS-084; 208 V single- and three-phase MCA/MFS columns. |
| q025 | Same PDF, p12 | 100°FDB / 69.2°FWB total MBH row; CRS-042-W and CRS-084-W column alignment. |
| q003, q026 | `STULZ CyberRow CW Engineering Manual QEWR001G.pdf`, p10 | CRS-090-C performance table; 12 in cabinet; 100°F or 95°F entering air section; 40°F EWT / 10°F ΔT; flow or total/sensible capacity and units. |
| q012 | Same PDF, p12 | Cooling-only electrical table; CRS-090-W versus CRS-180-W at 120 V / 1 PH / 60 Hz. |
| q019 | Same PDF, p6 | CyberRow chilled-water overview; independent valve and fan control in response to varying heat loads. |
| q004, q013–q014, q027 | `STULZ CyberOne DX Engineering Manual.pdf`, p24 | Multi-level model/MCA/MFS header; *Cooling Only* section; 208/3/60; condensate pump No versus Yes. |
| q005, q015 | `STULZ Heat Rejection Engineering Manual QECS008E.pdf`, p10 | SCS-MC performance table; R410A at 105°F for 015-S; hot-gas line column for 035-S versus 035-D. |
| q016, q028 | Same PDF, p12 | Unit dimensions, distinct from shipping dimensions; 031-S/D unit depth and 223-D (2x2)/(1x4) unit width/depth. |
| q006, q017 | `STULZ_Glycol_Systems_Engineering_Manual.pdf`, p15 | Single-row FSS drycooler table; separate 95°F and 105°F ambient sections; 40% ethylene glycol; flow and heat-rejection columns. |
| q020 | Same PDF, p5 | Text describing A, B, and C GPS pump variants and their head/flow applications. |
| q007 | `990_4705_InRow_Chilled_Water_Air_Conditioners_300_Installation_Manual.pdf`, p35 | Service Access paragraph; front and **rear** clearance. |
| q018 | Same PDF, pp15–16 | Separate ACRC301S and ACRC301H package-inventory tables; gasket descriptions and quantities. |
| q021–q022 | Same PDF, p24 | Room Preparation vapor-barrier purpose; ACRC301H chilled-water requirement relative to room dew point. |
| q008 | `FG_humiFog manual_maintenance_en.pdf`, p8 | Cabinet part number table; UA080DD100 pump capacity and single-zone designation. |
| q009, q023 | Same PDF, p12 | Feedwater characteristics table and prose; conductivity units and reasons for demineralised water. |
| q010 | `gks_65_gce_professional.pdf`, p8 | Bosch three-model technical-data table; GKS 65 GCE column and rated power input row. |
| q024 | Same PDF, p10 | Sawing Light Building Materials section; dry cutting, dust extraction, and guide rail. |
| q029–q030 | Corpus-wide; likely source for q030: CyberRow DX p13 | Verify the requested price and 400 V / 3 PH / 60 Hz CRS-084 MFS are absent from **all** relevant indexed manuals, including duplicate copies. |

## Labels needing particular attention

- **q003 and q026:** the CRS-090-C model caption occurs at the end of p10, outside the proposed `c1` chunk. Review whether `c1` alone should count as a relevant chunk or whether the caption chunk must also be labeled. The page-level label is separate.
- **q004, q013, q014, q027:** the CyberOne model headers and cooling-only data are split across chunks. Check every proposed chunk for independent relevance; keep only IDs justified under the intended chunk-level criterion.
- **q006, q017, q028:** flattened text crosses adjacent table sections or splits headers from data. Confirm values and associations directly on the PDF page. For q028, `c1` carries the Unit/Shipping header and `c2` carries both 223-D configurations.
- **q018:** the package inventories have two visual columns. Confirm each gasket quantity belongs to the named ACRC301 variant.
- **q029 and q030:** these are provisional no-answer questions. A text scan of all 50 indexed PDFs found no `price` or `msrp` text. It found `400 v` on Carel HumiSteam and RoofJETT pages, but not in the CyberRow DX manual; the CyberRow DX p13 table lists 208 V, 460 V, and 575 V rows. Text scanning can miss image-only content and wording variants, so a human must confirm both absence labels. All three relevance fields are blank as required for an `unanswerable` row.

No retrieval results or accuracy metrics have been computed from these candidates.
