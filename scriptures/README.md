# scriptures/ — Scripture Metadata Management App

This Django app manages **metadata about scripture collections and their PDF volumes**.
It tracks which scriptures are available, their file details, and indexing status.

## Purpose

While the `chat/rag/` subpackage handles the actual PDF loading and embedding, this app
provides:
- **Scripture registry**: A database record for each scripture collection (e.g., "Mahabharata")
- **Volume tracking**: Individual PDF file metadata (path, size, page count, modification time)
- **Indexing status**: Whether a scripture has been embedded and when
- **Admin interface**: Browse and manage scriptures from Django admin
- **Re-indexing API**: Trigger re-embedding from the API or admin

## Files

### `models.py` — Scripture & Volume Models

**`Scripture` model:**
- `name`: Unique name (e.g., "Mahabharata", "Ramayana")
- `folder_path`: Path to the scripture's folder under `data/docs/`
- `description`: Optional description text
- `total_volumes`: Number of PDF files
- `total_pages`: Total pages across all volumes
- `is_indexed`: Whether embeddings have been generated
- `last_indexed_at`: When embeddings were last updated
- Ordered alphabetically by name

**`Volume` model:**
- `scripture`: ForeignKey to Scripture (each volume belongs to one scripture)
- `file_name`: PDF filename
- `file_path`: Full path to the PDF file
- `file_size`: File size in bytes
- `page_count`: Number of pages
- `mtime`: File modification time (for change detection)
- Ordered by filename

### `serializers.py` — DRF Serializers

- **`VolumeSerializer`**: Serializes volume metadata
- **`ScriptureSerializer`**: Serializes scripture with nested volumes list

### `views.py` — ScriptureViewSet

A read-only ModelViewSet with a custom action:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `list` | `GET /api/scriptures/` | List all scriptures with volumes |
| `retrieve` | `GET /api/scriptures/<id>/` | Get scripture details |
| `reindex` | `POST /api/scriptures/<id>/reindex/` | Mark scripture for re-indexing |

### `urls.py`
Uses DRF's `DefaultRouter` for auto-generated routes.

### `admin.py` — ScriptureAdmin

- List display: name, total_volumes, total_pages, is_indexed, last_indexed_at
- Filterable by indexing status
- Searchable by name/description
- Inline Volume display (read-only)

### `apps.py`
Django app configuration. Sets `verbose_name = "Scripture Management"`.

## Tests

### `tests/test_models.py`
Tests for Scripture and Volume model creation and relationships.
(Not yet created — will be added in the testing phase.)
