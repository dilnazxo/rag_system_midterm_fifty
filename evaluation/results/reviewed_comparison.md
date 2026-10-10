# Retrieval comparison after five-question review

The same saved 6,209-chunk FAISS index was used for A (dense), B (model filtering), and C (filtering plus PDF deduplication). These are retrieval-label comparisons, not answer-generation scores.

## Verified labels — 3 questions

The user checked source answers for q010, q018, and q020. Their proposed chunk IDs were then checked independently against saved metadata and source-PDF text. No unanswerable question has a verified absence label.

| Mode | Document Hit@5 | Page Hit@5 | Chunk Recall@5 | Chunk MRR@5 | Model confusion | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| A | 100.0% (3 Q) | 66.7% (3 Q) | 66.7% (3 Q) | 66.7% (3 Q) | n/a | 64.5 ms |
| B | 100.0% (3 Q) | 66.7% (3 Q) | 66.7% (3 Q) | 66.7% (3 Q) | n/a | 21.9 ms |
| C | 100.0% (3 Q) | 66.7% (3 Q) | 66.7% (3 Q) | 66.7% (3 Q) | n/a | 25.3 ms |

q018 returned the right document but neither labeled page in the top five in all modes; q010 and q020 hit their labeled chunks. Model confusion is undefined because the existing classifier recognizes CyberRow/CyberOne family names only, and none of these three expected models are classifiable. The small sample cannot establish broad retrieval accuracy.

## PROVISIONAL / AUTO-LABELED — 30 candidates

The candidate set still has `verified=false` on all 30 rows. Its 28 answerable candidates contribute to document/page metrics and latency. Only eight structurally complete single-chunk-page candidates contribute to chunk Recall@5 and MRR@5. The two unanswerable candidates are excluded from answerable metrics and remain unverified.

| Mode | Document Hit@5 | Page Hit@5 | Chunk Recall@5 | Chunk MRR@5 | Model confusion | Mean latency |
|---|---:|---:|---:|---:|---:|---:|
| A | 82.1% (28 Q) | 53.6% (28 Q) | 62.5% (8 Q) | 53.1% (8 Q) | 55.2% (58 results) | 24.5 ms |
| B | 96.4% (28 Q) | 71.4% (28 Q) | 62.5% (8 Q) | 62.5% (8 Q) | 0.0% (60 results) | 21.0 ms |
| C | 96.4% (28 Q) | 78.6% (28 Q) | 75.0% (8 Q) | 65.6% (8 Q) | 0.0% (60 results) | 23.5 ms |

The provisional table overlaps the three verified questions but remains a separate, auto-labeled comparison of the full candidate set. Neither table treats a document label as a page or chunk label. MRR is shown as a percentage of its 0–1 scale. Latency is a single local pass per mode and should not be treated as a stable performance benchmark.

Sources: `verified/aggregate.json`, `verified/predictions_A.json` through `predictions_C.json`, `provisional/aggregate.json`, and `provisional/predictions_A.json` through `predictions_C.json`. See `../review_validation.md` for acceptance decisions and the original user review flags.
