# PROVISIONAL / AUTO-LABELED retrieval comparison

**Verified questions: 0.** Candidate labels passed structural checks only; none are verified accuracy. All modes used the same saved FAISS index.

| Mode | Document Hit@5 | Page Hit@5 | Chunk Recall@5* | Chunk MRR@5* | Model confusion | Mean latency (ms) | p95 latency (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 82.1% (28 Q) | 53.6% (28 Q) | 62.5% (8 Q) | 53.1% (8 Q) | 55.2% (58 results) | 24.5 | 27.0 |
| B | 96.4% (28 Q) | 71.4% (28 Q) | 62.5% (8 Q) | 62.5% (8 Q) | 0.0% (60 results) | 21.0 | 25.6 |
| C | 96.4% (28 Q) | 78.6% (28 Q) | 75.0% (8 Q) | 65.6% (8 Q) | 0.0% (60 results) | 23.5 | 27.7 |

*Chunk metrics use only candidate questions whose labeled PDF page has exactly one saved chunk per page and whose label lists that chunk. This is structural completeness, not human judgment of semantic relevance.*

Document and page metrics use 28 answerable candidates. MRR is displayed as a percentage of its 0–1 scale. Mean and p95 latency also use the 28 answerable candidates. The two provisional unanswerable candidates are excluded from all answerable-only metrics and timed separately in `aggregate.json`; no absence or abstention score is claimed.

Model confusion covers only recognizable CyberRow/CyberOne family results; other equipment families are outside the existing classifier. Latency is one local pass per mode, including encoding and FAISS search but excluding index/model loading. Mode order and caching can affect timing.

Automatic validation checks exact PDF filenames and hashes, page bounds, chunk IDs and document/page alignment, and regeneration of saved chunk text from each source page. It cannot establish correct table cell associations, semantic relevance, exhaustive labels, or absence from image-only PDF content.

Files: `questions_provisional.csv`, `label_validation.json`, `predictions_A.json`, `predictions_B.json`, `predictions_C.json`, `aggregate.json`, `quick_review.md`.
