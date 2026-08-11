# Scripture Catalog And Indexing

## Purpose

`scriptures/` manages discovered spiritual-text collections, source volumes,
immutable index versions, candidate qualification, and atomic activation.
Collection names are data, never product-code constants.

## Architecture And Data Flow

Folders under the configured document root are discovered dynamically. The
operations scheduler periodically scans `data/docs/<Collection Name>/*.pdf`,
creates missing scripture records, and queues one indexing job per unindexed
collection. Each PDF becomes a volume record. Celery builds a candidate index
version, records counts and qualification results, runs retrieval smoke checks,
then activates the candidate transactionally. The previous complete version
remains available for rollback. Candidate embedding commits update durable
chunk counts and progress after every batch, so long first-time builds remain
observable. Task retries resume a source-identical candidate from its committed
chunk count; changed source manifests fail closed instead of mixing versions.
If the PDF text layer is corrupt, indexing falls back to local OCR before
rejecting the candidate. OCR output must pass the same source-quality and
retrieval-smoke gates before activation.

## Files And Entrypoints

- `models.py`: scripture, volume, index version, and indexing job records.
- `tasks.py`: candidate build, qualification, activation, and failure handling.
- `views.py`: cursor-paginated status and staff indexing actions.
- `serializers.py`: bounded public API shapes.
- `admin.py`: staff inspection and controls.

## Interfaces

The versioned API lists discovered collections and indexing status. Staff
actions enqueue indexing; they do not perform heavy model work inside HTTP
requests.

## Configuration

Set the document root, embedding service URL, retrieval thresholds, OCR engine,
Celery index queue, and `SCRIPTURE_AUTO_DISCOVER_SECONDS` schedule. Adding a
folder with PDFs is enough for scheduled discovery and automatic indexing.

OCR defaults to Tesseract 5 LSTM through
`SCRIPTURE_OCR_TESSERACT_CMD=D:\Softwares\Tesseract\tesseract.exe` with
`SCRIPTURE_OCR_LANGUAGES=Devanagari+eng`, `SCRIPTURE_OCR_DPI=250`, and
`SCRIPTURE_OCR_PSM=4`. Keep Devanagari script and English traineddata under the
configured tessdata directory. This runs on CPU and fits the local laptop
profile; no scripture text is sent to a remote OCR service. OCR output is
cached per source file, page, model, DPI, and page-segmentation mode under
`data/ocr-cache`, so interrupted large-corpus builds can resume without
reprocessing completed pages.

## Commands

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\Ninad\Python\.env'
uv run --no-cache python manage.py discover_scriptures
uv run --no-cache python manage.py discover_scriptures --resume-running
uv run --no-cache celery -A moksha worker -Q indexing --loglevel=INFO
```

Discovery skips completed collections unless `--force` is supplied, resumes a
pending job, and leaves an already running job untouched. Use
`--resume-running` only after confirming the original worker or synchronous
command has stopped; it resumes source-identical committed candidate chunks.

## Tests

Model and API tests live under `scriptures/tests/`. Integration gates require
real PostgreSQL/PgVector, Redis, Celery, the embedding service, and a retrieval
smoke query against the candidate version.

## Dependencies

Django, DRF, Celery, PostgreSQL/PgVector, PyMuPDF, and the private embedding
service.

## Security

Only staff can trigger or activate indexing. File paths remain server-side.
Activation requires a complete qualified candidate and uses a DB transaction.

## Failure Modes And Troubleshooting

- No collections: verify document root and PDF folder layout.
- Candidate rejected: inspect bounded qualification codes and retrieval smoke.
- `index_source_text_corrupt`: PDF font mapping produced mojibake and local OCR
  is disabled.
- `index_ocr_unavailable`: local OCR executable or requested language model is
  missing. Install Tesseract and `Devanagari`, `eng` traineddata, then retry.
- `index_ocr_quality_failed`: OCR ran, but the output still failed exact-verse
  quality checks. Inspect the source scan quality before forcing any index.
- Activation conflict: retry after active indexing job finishes.
- Embedding errors: check private sidecar health and queue logs.

## Related Docs

See `../chat/rag/README.md`, `../embedding_service/README.md`,
`../operations/README.md`, and `../deploy/README.md`.
