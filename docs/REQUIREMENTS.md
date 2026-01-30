# Requirements — Markdown Search & Upload App (FastAPI)

## 1) Goal

Build a single FastAPI web application that indexes markdown files stored outside the project folder, allows searching/browsing and viewing markdown, supports authenticated uploads, and can auto-generate titles/descriptions via OpenAI when missing.

Make the applicaiton modularized. For local testing let's creat the venv inside the project folder but it should not be tracked by git so the venv should be correctly listed in the .gitignore file.

---

## 2) Storage & Environment

### 2.1 Environment variables (.env)

- `PATH_PROJECT_RESOURCES`: absolute path to an external directory (outside the project repo).
- `EMAIL_ADMIN_USER`: admin email used for login / verification target.
- Gmail SMTP settings for sending verification emails (e.g., `GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD`, `GMAIL_SMTP_HOST`, `GMAIL_SMTP_PORT`).
- OpenAI API settings (e.g., `OPENAI_API_KEY`).

### 2.2 Required directory layout (inside `PATH_PROJECT_RESOURCES`)

- `markdown_files/` — all markdown files stored here.
- `database/` — CSV (or JSON if needed) stored here.
- `prompts/` — external prompt templates stored here.

Example:

```
PATH_PROJECT_RESOURCES/
  markdown_files/
  database/
    index.csv
  prompts/
    summarize_markdown.md
```

---

## 3) Data Model (CSV-first “database”)

Primary index file: `PATH_PROJECT_RESOURCES/database/index.csv`

### 3.1 Columns

- `filename` (string) — **required**
- `title` (string) — optional
- `description` (string) — optional
- `is_public` (boolean) — required for access control (default to `true` if unspecified on upload)
- `date_uploaded` (YYYY-MM-DD) — **required**
- (Optional) `updated_at` (timestamp) — useful but not required

### 3.2 Rules

- `filename` must match an actual file under `markdown_files/`.
- `filename` is the unique key:
  - If CSV already contains `filename`, do not create a duplicate row.
- CSV is the source of truth for metadata; files are the source of truth for content.

---

## 4) Pages & UX

### 4.1 Navigation (top)

- Always visible:
  - Home link
  - Login/Logout button
- Visible when logged in:
  - Upload link/button
  - “Review and Process Markdowns” button on Upload page

### 4.2 Home page (public)

- Responsive layout:
  - Mobile/narrow: search bar at top, list/table below.
  - Wide screen: left pane search, right pane table/list of results.
- Displays:
  - For non-logged-in users: only rows with `is_public = true`.
  - For logged-in users: all rows.
- Search:
  - Filters by filename/title/description (case-insensitive).
  - Click a row to open the markdown viewer page.

### 4.3 Markdown viewer page

- Renders selected markdown as HTML.
- Applies same access rules:
  - Non-logged-in users cannot open private files.
  - Logged-in users can open all.

### 4.4 Manage Files page (authenticated only)

- Collapsable sections
  - Upload new file
  - Review and Process Markdowns
- File upload input (accept `.md`, optionally `.markdown`).
- Metadata inputs:
  - `filename` and `date_uploaded` auto-populated upon upload:
    - `filename` from uploaded file name (sanitized; collisions handled)
    - `date_uploaded` set to current server date
  - `title`, `description`, `is_public` optional (except `is_public` needs a default)
  - by default all files will be private.
- On submit:
  - Save file into `PATH_PROJECT_RESOURCES/markdown_files/`
  - Insert or update CSV row for that `filename` (no duplicates)
- Bottom section "Manage Existing Files"
  - table that lists files and allows the user to toggle between private and public.
  - button to delete a file in each row.
  - Button at the bottom of this section to update the metadata of all files.

### 4.5 Style

- use grays and green colors. I would like this to have a terminal vibe. Use a dark background and light text. Please allow for a light a dark theme. Where we have a toggle on the navigation bar. If possible make the selection persistent.

---

## 5) Authentication & Email Verification

### 5.1 Authentication behavior

- Only verified users can log in.
- Persist login across browser sessions (secure cookie session).

### 5.2 Email verification flow

- Login page asks for email.
- If email matches `EMAIL_ADMIN_USER`:
  - Generate single-use, time-limited verification token.
  - Send verification link/code via Gmail SMTP using app password.
- Verification endpoint:
  - Validates token and creates authenticated session.
- Logout endpoint clears session.

---

## 6) OpenAI Auto-Metadata Generation

### 6.1 When to call OpenAI

If an uploaded file has missing `title` or `description`:

- Read the markdown file content.
- Send content to OpenAI model `gpt-4o-mini` to generate:
  - A concise `title`
  - A 1–3 sentence `description` (animated tone, include emojis where appropriate)
- Store generated values back into the CSV row.

### 6.2 Prompt template stored externally

- Store prompt template under:
  - `PATH_PROJECT_RESOURCES/prompts/summarize_markdown.md` (recommended)
- Template must include a placeholder such as:
  - `{markdown_file_content}`
- Application loads this file at runtime and substitutes the placeholder with the markdown content prior to the OpenAI call.
- Prompt file must be editable without modifying the project repo.

### 6.3 Fallback behavior

- If the API returns no response or an invalid response:
  - Leave `title` and/or `description` blank (do not block upload/process).

---

## 7) “Review and Process Markdowns” (authenticated only)

### 7.1 Behavior

Triggered by a button on the Upload page:

- Scan `PATH_PROJECT_RESOURCES/markdown_files/` for files.
- Compare filenames to CSV `index.csv`.
- For each file not present in CSV:
  - Append a new CSV row with:
    - `filename` = file name
    - `date_uploaded` = current date
    - `title`/`description` blank initially
    - `is_public` default (e.g., true unless policy says otherwise)
  - Process files one at a time:
    - Call OpenAI to generate title/description using the external prompt template.
    - Save results to CSV when valid.
- For each file already in CSV:
  - Do nothing (no re-processing).

### 7.2 Output

- Show a summary in the UI:
  - Number of new files found
  - Number successfully enriched
  - Number skipped (already indexed)
  - Any errors (non-fatal)

---

## 8) Non-Functional Requirements

- Works on local machine and server.
- Robust file/path handling:
  - Ensure `PATH_PROJECT_RESOURCES` exists; create required subdirectories if missing.
- Security:
  - Secure session cookies (HttpOnly, SameSite, HTTPS settings when deployed).
  - Upload sanitization (prevent path traversal; restrict extensions).
- Reliability:
  - CSV writes must be atomic (write temp + replace).
  - Concurrency-safe enough for single-admin usage (lock file during write recommended).

---

## 9) Suggested Implementation Stack (informational)

- FastAPI + Jinja2 templates
- TailwindCSS for responsive layout
- HTMX for live search and partial page updates (optional but recommended)
- Markdown rendering library (e.g., `markdown-it-py` or `python-markdown`)
- SMTP email via Gmail app password
- OpenAI API client for `gpt-4o-mini`
- Logging use the guidance in the docs/LOGGING_PYTHON_V05.md file for logging
- Create a README.md file in the root directory of the project that follows the guidance in the docs/README-format.md file.
