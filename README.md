# TheDocs

## Project Overview

TheDocs is a FastAPI web app for indexing, searching, and viewing external markdown files with optional OpenAI-powered metadata enrichment. It uses Jinja2 templates, Loguru logging, and a CSV-based index for lightweight storage.

## Setup

1. Create a virtual environment in the project root: `python3 -m venv venv`.
2. Activate it: `source venv/bin/activate`.
3. Install dependencies: `pip install -r requirements.txt`.

## Usage

1. Set the required environment variables in `.env`.
2. Start Elasticsearch locally (example Docker command):
   - `docker run -p 9200:9200 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:8.12.2`
3. Run the server: `uvicorn app.main:app --reload`.
   - use `./venv/bin/uvicorn app.main:app --reload` or `python -m uvicorn app.main:app --reload` locally.
4. Open the app at `http://127.0.0.1:8000`.

## Project Structure

```
TheDocs/
├── app/
│   ├── core/
│   │   ├── config.py          # Environment config loader
│   │   ├── logging.py         # Loguru configuration
│   │   └── security.py        # Token generation/verification
│   ├── services/
│   │   ├── email_service.py   # SMTP email sender
│   │   ├── index_store.py     # CSV and file store utilities
│   │   ├── openai_client.py   # OpenAI metadata helper
│   │   └── search_service.py   # Elasticsearch integration
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css     # App styling
│   │   └── js/
│   │       ├── theme.js       # Theme persistence
│   │       └── search.js      # Live search
│   ├── templates/
│   │   ├── base.html          # Layout and navigation
│   │   ├── home.html          # Search and listing
│   │   ├── login.html         # Email login
│   │   ├── manage.html        # Upload and processing
│   │   └── viewer.html        # Markdown viewer
│   └── main.py                # FastAPI application
├── docs/
│   ├── LOGGING_PYTHON_V05.md
│   ├── README-format.md
│   └── REQUIREMENTS.md
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

## .env

```
PATH_PROJECT_RESOURCES=
EMAIL_ADMIN_USER=
GMAIL_SMTP_USER=
GMAIL_SMTP_APP_PASSWORD=
GMAIL_SMTP_HOST=
GMAIL_SMTP_PORT=
OPENAI_API_KEY=
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=thedocs-markdown
ELASTICSEARCH_USERNAME=
ELASTICSEARCH_PASSWORD=
SECRET_KEY=
NAME_APP=TheDocs
RUN_ENVIRONMENT=development
PATH_TO_LOGS=
TOKEN_TTL_MINUTES=15
LOG_MAX_SIZE=5 MB
LOG_MAX_FILES=5
```

## External Files

### PATH_PROJECT_RESOURCES/markdown_files/

- Stores uploaded markdown files (`.md`, `.markdown`).

### PATH_PROJECT_RESOURCES/database/index.csv

- CSV index used as the metadata store.
- Columns:
  - `filename` (unique key, required)
  - `title`
  - `description`
  - `is_public`
  - `date_uploaded`
  - `updated_at`

### PATH_PROJECT_RESOURCES/prompts/summarize_markdown.md

- Prompt template for OpenAI metadata generation.
- Must include `{markdown_file_content}` placeholder.

## References

- docs/LOGGING_PYTHON_V05.md
- docs/README-format.md

```

```
