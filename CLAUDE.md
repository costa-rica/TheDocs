# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TheDocs is a FastAPI web application for indexing, searching, and viewing external markdown files with optional OpenAI-powered metadata enrichment. The app uses Jinja2 templates, Loguru logging, a CSV-based index store, and supports both lexicon-based search (default) and Elasticsearch-based search (optional).

## Development Commands

### Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run with uvicorn (use one of these)
PYTHONPATH=src uvicorn app.main:app --reload
PYTHONPATH=src ./venv/bin/uvicorn app.main:app --reload
PYTHONPATH=src python -m uvicorn app.main:app --reload

# Alternative using --app-dir
uvicorn app.main:app --reload --app-dir src
python -m uvicorn app.main:app --reload --app-dir src
```

### Elasticsearch (Optional)
```bash
# Start Elasticsearch for semantic search
docker run -p 9200:9200 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:8.12.2
```

## Architecture

### Application Layout

The codebase follows a clean separation of concerns with a `src/app` layout:

- **`src/app/main.py`**: FastAPI application entry point containing all routes and request handlers
- **`src/app/core/`**: Configuration, logging, and security utilities
  - `config.py`: Environment variable loading via dataclass
  - `logging.py`: Loguru configuration
  - `security.py`: Token generation/verification using itsdangerous
- **`src/app/services/`**: Business logic services
  - `index_store.py`: CSV-based metadata store with file locking
  - `search_service.py`: Elasticsearch integration with fallback support
  - `openai_client.py`: OpenAI metadata generation
  - `email_service.py`: SMTP email verification
- **`src/app/templates/`**: Jinja2 HTML templates
- **`src/app/static/`**: CSS and JavaScript assets

### Key Architectural Patterns

**Dual Search Strategy**: The search system uses a strategy pattern where Elasticsearch is optional. If `ELASTICSEARCH_URL` is not set, the app automatically falls back to lexicon-based file scanning (`_fallback_search()` in main.py:144). This allows the app to function without external dependencies.

**CSV-based Metadata Store**: Instead of a traditional database, the app uses `IndexStore` (index_store.py) which manages a CSV file at `PATH_PROJECT_RESOURCES/database/index.csv`. File locking via `filelock` ensures safe concurrent access. The CSV stores:
- `filename` (unique key)
- `title`, `description` (enriched via OpenAI)
- `is_public` (visibility control)
- `date_uploaded`, `updated_at`

**Email-based Authentication**: The app uses a passwordless authentication flow. Users request a login link via email, which contains a time-limited token generated using `itsdangerous.URLSafeTimedSerializer`. Only the single admin email (`EMAIL_ADMIN_USER`) can authenticate.

**OpenAI Metadata Enrichment**: When files are uploaded or processed, the app optionally calls OpenAI to generate title/description metadata. The prompt template is loaded from `PATH_PROJECT_RESOURCES/prompts/summarize_markdown.md` and must include a `{markdown_file_content}` placeholder.

### External File Dependencies

The app requires an external directory (`PATH_PROJECT_RESOURCES`) with specific subdirectories:
- `markdown_files/`: Uploaded markdown files
- `database/`: Contains `index.csv` metadata store
- `prompts/`: Contains `summarize_markdown.md` prompt template

### Search Behavior

**Lexicon Search** (default): Case-insensitive substring matching with context windows. Supports phrase search via double quotes (e.g., `"release notes"`).

**Elasticsearch Search** (optional): Full-text search with highlighting. Automatically enabled when `ELASTICSEARCH_URL` is set. The `SearchService` handles index creation, document CRUD, and query building with support for phrase matching and wildcard queries.

## Environment Configuration

Required variables:
- `PATH_PROJECT_RESOURCES`: Base path for external files
- `EMAIL_ADMIN_USER`: Single authorized admin email
- `SECRET_KEY`: Used for session management and token signing
- SMTP credentials for email verification

Optional variables:
- `OPENAI_API_KEY`: Enables metadata enrichment
- `ELASTICSEARCH_URL`: Enables Elasticsearch search
- `TOKEN_TTL_MINUTES`: Login token validity (default: 15)

See `.env.example` for full configuration template.

## Code Patterns

**Session Management**: Uses Starlette's `SessionMiddleware` with helper functions (`_is_authenticated()`, `_flash()`, `_pop_flash()`) for authentication state and flash messages.

**Path Safety**: File access uses path resolution checks to prevent directory traversal (main.py:237-239).

**Atomic CSV Writes**: The `IndexStore._write_rows()` method uses `tempfile.NamedTemporaryFile` + `os.replace()` for atomic writes.

**Error Handling**: All Elasticsearch and OpenAI operations are wrapped in try/except blocks that log warnings and gracefully degrade functionality.
