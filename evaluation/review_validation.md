# Review update and evidence boundary

`human_review_submissions.csv` preserves the five user-supplied review records verbatim. Its `chunk_id_checked=false` entries mean the user did not check the saved chunks. They have not been changed to `true`.

The user confirmed the source-PDF answers for q010, q018, and q020. An independent check compared each proposed chunk ID in `data/index/chunks.json` with the exact source PDF filename, page number, PDF SHA-256, and text on that page. The proposed chunks contain the following answer evidence:

| ID | User-checked PDF answer | Independently checked chunk evidence | Accepted into `questions.csv` |
|---|---|---|---|
| q010 | 1800 W | `gks_65_gce_professional.pdf:p8:c4` contains the GKS 65 GCE header and the rated-input row ending in 1800 W. | Yes |
| q018 | ACRC301H | `...:p15:c1` contains ACRC301S and four pipe gaskets; `...:p16:c1` contains ACRC301H and two unit-pipe gaskets. Both IDs are from the named indexed PDF. | Yes |
| q020 | GPS A variant | `STULZ_Glycol_Systems_Engineering_Manual.pdf:p5:c1` states that A models suit high head pressure and low flow rate. | Yes |
| q027 | Provisional +2.1 A | The user could not verify the original CyberOne DX source. No verified answer or label was accepted. | No |
| q029 | Price not stated in checked manual | Only the checked CyberRow DX manual was reviewed. Corpus-wide absence remains unverified. | No |

The five records remain in the 30-row `questions_candidates.csv` with `verified=false` as candidate history. Only the three fully supported rows were copied to `questions.csv` with `verified=true`. The Stage 5.1 verified runner reads `questions.csv`; the separate provisional runner reads all 30 candidates. Its metrics remain **PROVISIONAL / AUTO-LABELED**, including the three rows that also have a verified record, because that run scores the complete candidate set.
