# Stage 5.1 retrieval evaluation

This framework reads the saved `data/index/chunks.faiss` and `chunks.json`. It never builds an index or reads PDF content. The index checksum, type and chunk count are checked before evaluation. Query embeddings use the locally cached `sentence-transformers/all-MiniLM-L6-v2` model; a missing local model stops the run instead of downloading one. No LLM is called.

## Prepare ground truth

Edit `questions.csv`. It intentionally contains only the required header. Use one row per human-written question and a unique `question_id`. Set `verified=true` only after checking the relevance labels against the manuals and saved chunks.

| Field | Format |
|---|---|
| `question_id` | Unique identifier. |
| `question` | Human-written query. |
| `expected_model` | One family such as `CyberRow DX` when model confusion should be measured. It is **never** used to filter retrieval. |
| `relevant_document` | Exact indexed PDF filename. Separate multiple filenames with `|`. |
| `relevant_pages` | One-based pages separated by `|`. Bare page numbers require exactly one `relevant_document`; otherwise use `filename.pdf:p13`. |
| `relevant_chunk_ids` | Exact saved chunk IDs separated by `|`. |
| `question_type` | Descriptive type, or exactly `unanswerable` for a verified no-answer question. |
| `verified` | `true`/`yes`/`1` for reviewed ground truth; blank/false rows are excluded. |

An answerable verified row needs at least one relevance level. A verified `unanswerable` row must leave all three relevance fields blank. Document labels do **not** imply that any page or chunk is relevant. Page labels do **not** imply that any chunk is relevant. Invalid verified rows are excluded with a reason in `results/excluded_rows.json`.

Exact duplicate PDFs are equivalent for judging document, page and chunk hits: filenames are canonicalized using the saved PDF SHA-256 list. At chunk level, equivalent copies use the same page and chunk ordinal. Predictions retain their actual indexed filenames and chunk IDs for audit.

## Configurations

All modes use the same query encoder, saved FAISS vectors and top five ranking:

- **A:** dense retrieval without model filtering or PDF deduplication.
- **B:** dense retrieval with production-style model filtering only.
- **C:** dense retrieval with production-style model filtering and PDF deduplication.

Model filtering reads explicit equipment-family words from the **question**, as production search does. It never uses `expected_model` or any relevance label. A question without a recognized family remains unfiltered in B and C.

## Metrics and denominators

- **Recall@5:** macro mean of each question's fraction of explicitly relevant *chunks* returned in the top five. Denominator: verified answerable questions with at least one `relevant_chunk_ids` label. Duplicate-copy equivalents count as one relevant chunk.
- **MRR@5:** macro mean reciprocal rank of the first explicitly relevant chunk in the top five, or zero if absent. Same question denominator as Recall@5.
- **Document hit@5:** fraction of verified answerable questions with at least one `relevant_document` whose top five contain an equivalent document. Denominator: such document-labeled questions only.
- **Page hit@5:** analogous extra metric using explicit `(document, page)` labels. Denominator: verified answerable questions with `relevant_pages`.
- **Model confusion rate:** wrong-family returned chunks divided by returned chunks with exactly one recognizable filename family, among verified answerable questions with exactly one recognizable `expected_model` family. Unclassifiable result filenames and missing/ambiguous expected models are excluded from this denominator and counted separately.
- **Retrieval latency:** mean and nearest-rank p95 milliseconds over all evaluated verified rows, including verified unanswerable rows. Each timed call includes query encoding, FAISS search and filtering; saved-index and model loading are excluded. A single pass is a timing sample, not a performance benchmark.

Verified unanswerable rows contribute only to latency. They are excluded from relevance and model-confusion denominators; this framework has no abstention metric. Any metric with a zero denominator is `null`, not zero. Coverage and excluded-row counts are reported separately from metrics.

## Run

From the project root:

```powershell
.venv/Scripts/python.exe -m evaluation.evaluate
.venv/Scripts/python.exe -m unittest -v evaluation.test_evaluation
```

The run writes `results/predictions_A.json`, `predictions_B.json`, `predictions_C.json`, `aggregate.json` and `excluded_rows.json`. A header-only question template produces empty prediction lists and `null` metrics; it does not generate questions or scores.
