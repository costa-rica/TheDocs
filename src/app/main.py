import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from markdown_it import MarkdownIt
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import load_config
from app.core.logging import configure_logging
from app.core.security import build_serializer, generate_verification_token, verify_token
from app.services.email_service import send_verification_email
from app.services.index_store import IndexStore
from app.services.openai_client import OpenAIService
from app.services.search_service import SearchResult, SearchService

load_dotenv()
configure_logging()
config = load_config()

if not config.path_project_resources:
    logger.error("Missing required environment variable: PATH_PROJECT_RESOURCES")
    raise SystemExit(1)
if not config.email_admin_user:
    logger.error("Missing required environment variable: EMAIL_ADMIN_USER")
    raise SystemExit(1)
if not config.secret_key:
    logger.error("Missing required environment variable: SECRET_KEY")
    raise SystemExit(1)

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=config.secret_key,
    same_site="lax",
    https_only=config.run_environment == "production",
    max_age=60 * 60 * 24 * 30,
)

templates = Jinja2Templates(directory="src/app/templates")
app.mount("/static", StaticFiles(directory="src/app/static"), name="static")

markdown = MarkdownIt("commonmark", {"html": True, "linkify": True})

store = IndexStore(config.path_project_resources)
store.ensure_directories()

openai_service = OpenAIService(config.openai_api_key)
search_service = SearchService(
    url=config.elasticsearch_url,
    index_name=config.elasticsearch_index,
    username=config.elasticsearch_username,
    password=config.elasticsearch_password,
)
serializer = build_serializer(config.secret_key)

TOKEN_TTL_MINUTES = int(os.getenv("TOKEN_TTL_MINUTES", "15"))


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("is_authenticated"))


def _flash(request: Request, key: str, value: Any) -> None:
    request.session[key] = value


def _pop_flash(request: Request, key: str) -> Any:
    return request.session.pop(key, None)


def _load_prompt(markdown_text: str) -> str:
    prompt_path = store.prompts_dir / "summarize_markdown.md"
    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8")
    else:
        logger.warning("Prompt template not found; using fallback prompt")
        template = (
            "Summarize the markdown and return JSON with keys title and description. "
            "Use a concise title and a 1-3 sentence description with an animated tone and "
            "emojis where appropriate.\nMarkdown:\n{markdown_file_content}"
        )
    return template.replace("{markdown_file_content}", markdown_text)


def _index_markdown_files(filenames: List[str]) -> None:
    if not search_service.is_enabled():
        return
    rows = {row.filename: row.is_public for row in store.list_rows()}
    for filename in filenames:
        path = store.markdown_dir / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        is_public = rows.get(filename, False)
        search_service.index_document(filename, content, is_public)


def _build_metadata_updates(
    filenames: List[str],
    existing: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, Dict[str, str]], int]:
    updates: Dict[str, Dict[str, str]] = {}
    errors = 0
    for filename in filenames:
        path = store.markdown_dir / filename
        if not path.exists():
            errors += 1
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        prompt = _load_prompt(content)
        generated = openai_service.generate_metadata(prompt)
        if not generated:
            errors += 1
            continue
        title = generated.get("title", "").strip()
        description = generated.get("description", "").strip()
        payload: Dict[str, str] = {}
        if title and not existing.get(filename, {}).get("title"):
            payload["title"] = title
        if description and not existing.get(filename, {}).get("description"):
            payload["description"] = description
        if payload:
            updates[filename] = payload
    return updates, errors


def _run_search(query: str, is_authenticated: bool) -> List[SearchResult]:
    public_only = not is_authenticated
    if search_service.is_enabled():
        results = search_service.search(query, public_only=public_only, size=50)
        if results is not None:
            return results
    return _fallback_search(query, public_only=public_only)


def _fallback_search(query: str, public_only: bool) -> List[SearchResult]:
    query = query.strip()
    if not query:
        return []
    rows = store.list_rows()
    if public_only:
        rows = [row for row in rows if row.is_public]

    phrase = _extract_phrase(query)
    term = phrase or query
    results: List[SearchResult] = []
    window = 25
    for row in rows:
        path = store.markdown_dir / row.filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        matches = _find_matches(content, term)
        for start in matches:
            end = start + len(term)
            snippet_start = max(start - window, 0)
            snippet_end = min(end + window, len(content))
            snippet = content[snippet_start:snippet_end]
            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(content):
                snippet = snippet + "..."
            results.append(SearchResult(snippet=snippet, filename=row.filename))
    return results[:100]


def _extract_phrase(query: str) -> Optional[str]:
    match = re.search(r"\"([^\"]+)\"", query)
    return match.group(1).strip() if match else None


def _find_matches(content: str, term: str) -> List[int]:
    if not term:
        return []
    content_lower = content.lower()
    term_lower = term.lower()
    indexes: List[int] = []
    start = 0
    while True:
        idx = content_lower.find(term_lower, start)
        if idx == -1:
            break
        indexes.append(idx)
        start = idx + len(term_lower)
    return indexes


@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: Optional[str] = None):
    query = (q or "").strip()
    results: List[SearchResult] = []
    if query:
        results = _run_search(query, _is_authenticated(request))
    rows = store.list_rows()
    if not _is_authenticated(request):
        rows = [row for row in rows if row.is_public]

    context = {
        "request": request,
        "results": results,
        "rows": rows,
        "query": q or "",
        "is_authenticated": _is_authenticated(request),
        "page_title": "TheDocs",
    }
    return templates.TemplateResponse("home.html", context)


@app.get("/search")
def search(request: Request, q: Optional[str] = None):
    query = (q or "").strip()
    results = _run_search(query, _is_authenticated(request))
    payload = {
        "query": query,
        "count": len(results),
        "results": [{"snippet": r.snippet, "filename": r.filename} for r in results],
    }
    return JSONResponse(payload)


@app.get("/markdown/{filename}", response_class=HTMLResponse)
def view_markdown(request: Request, filename: str):
    row = store.get_row(filename)
    if not row:
        raise HTTPException(status_code=404, detail="File not indexed")
    if not row.is_public and not _is_authenticated(request):
        raise HTTPException(status_code=403, detail="Private file")

    safe_path = (store.markdown_dir / filename).resolve()
    if store.markdown_dir.resolve() not in safe_path.parents:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File missing")

    content = safe_path.read_text(encoding="utf-8", errors="ignore")
    html = markdown.render(content)
    context = {
        "request": request,
        "filename": row.filename,
        "title": row.title,
        "description": row.description,
        "content": html,
        "is_public": row.is_public,
        "is_authenticated": _is_authenticated(request),
        "page_title": row.title or row.filename,
    }
    return templates.TemplateResponse("viewer.html", context)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    context = {
        "request": request,
        "notice": _pop_flash(request, "notice"),
        "error": _pop_flash(request, "error"),
        "is_authenticated": _is_authenticated(request),
        "page_title": "Login",
    }
    return templates.TemplateResponse("login.html", context)


@app.post("/login")
def login(request: Request, email: str = Form(...)):
    email = email.strip().lower()
    if email != config.email_admin_user.lower():
        _flash(request, "error", "Email not authorized for admin access.")
        return RedirectResponse(url="/login", status_code=303)

    token = generate_verification_token(serializer, email)
    verify_url = f"{request.url_for('verify_email')}?token={token}"
    sent = send_verification_email(
        smtp_host=config.gmail_smtp_host,
        smtp_port=config.gmail_smtp_port,
        smtp_user=config.gmail_smtp_user,
        smtp_password=config.gmail_smtp_app_password,
        to_email=email,
        verification_url=verify_url,
    )
    if sent:
        _flash(request, "notice", "Verification email sent. Check your inbox.")
    else:
        _flash(request, "error", "Email failed to send. Check SMTP settings.")
    return RedirectResponse(url="/login", status_code=303)


@app.get("/verify", name="verify_email")
def verify_email(request: Request, token: str):
    email = verify_token(serializer, token, TOKEN_TTL_MINUTES * 60)
    if not email or email.lower() != config.email_admin_user.lower():
        _flash(request, "error", "Verification link invalid or expired.")
        return RedirectResponse(url="/login", status_code=303)

    request.session["is_authenticated"] = True
    request.session["email"] = email
    _flash(request, "notice", "You are now logged in.")
    return RedirectResponse(url="/manage", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/manage", response_class=HTMLResponse)
def manage(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    context = {
        "request": request,
        "rows": store.list_rows(),
        "notice": _pop_flash(request, "notice"),
        "error": _pop_flash(request, "error"),
        "process_summary": _pop_flash(request, "process_summary"),
        "is_authenticated": _is_authenticated(request),
        "page_title": "Manage",
    }
    return templates.TemplateResponse("manage.html", context)


@app.post("/manage/upload")
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    description: str = Form(""),
    is_public: Optional[str] = Form(None),
):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    try:
        content = file.file.read()
        original_name = file.filename or "upload.md"
        filename = store.save_markdown_file(original_name, content)
    except ValueError:
        _flash(request, "error", "Unsupported file type.")
        return RedirectResponse(url="/manage", status_code=303)

    public_flag = bool(is_public)
    row = store.build_row(
        filename=filename,
        title=title.strip(),
        description=description.strip(),
        is_public=public_flag,
        date_uploaded=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    store.upsert_row(row)

    existing = {filename: {"title": row.title, "description": row.description}}
    updates, _errors = _build_metadata_updates([filename], existing)
    store.update_missing_metadata(updates)

    _index_markdown_files([filename])

    _flash(request, "notice", f"Uploaded {filename}.")
    return RedirectResponse(url="/manage", status_code=303)


@app.post("/manage/process")
def process_markdowns(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    default_public = False
    new_files = store.sync_new_files(default_public)
    rows = store.list_rows()
    existing_rows = {row.filename: {"title": row.title, "description": row.description} for row in rows}
    missing_existing = [row.filename for row in rows if not row.title or not row.description]
    candidates = sorted(set(new_files + missing_existing))
    updates, errors = _build_metadata_updates(candidates, existing_rows)
    store.update_missing_metadata(updates)

    _index_markdown_files(store.list_markdown_files())

    total_indexed = len(rows)
    skipped = max(total_indexed - len(new_files) - len(missing_existing), 0)
    summary = {
        "new_files": len(new_files),
        "enriched": len(updates),
        "skipped": skipped,
        "errors": errors,
    }
    _flash(request, "process_summary", summary)
    return RedirectResponse(url="/manage", status_code=303)


@app.post("/manage/toggle")
def toggle_visibility(request: Request, filename: str = Form(...), is_public: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    store.toggle_public(filename, is_public == "true")
    search_service.update_visibility(filename, is_public == "true")
    _flash(request, "notice", f"Updated visibility for {filename}.")
    return RedirectResponse(url="/manage", status_code=303)


@app.post("/manage/delete")
def delete_file(request: Request, filename: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    store.delete_markdown_file(filename)
    store.delete_row(filename)
    search_service.delete_document(filename)
    _flash(request, "notice", f"Deleted {filename}.")
    return RedirectResponse(url="/manage", status_code=303)


@app.post("/manage/update-metadata")
def update_metadata(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    rows = store.list_rows()
    missing = [row.filename for row in rows if not row.title or not row.description]
    existing = {row.filename: {"title": row.title, "description": row.description} for row in rows}
    updates, errors = _build_metadata_updates(missing, existing)
    store.update_missing_metadata(updates)
    _flash(
        request,
        "notice",
        f"Updated metadata for {len(updates)} file(s). Errors: {errors}.",
    )
    return RedirectResponse(url="/manage", status_code=303)
