import csv
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from filelock import FileLock

ALLOWED_EXTENSIONS = {".md", ".markdown"}
CSV_COLUMNS = ["filename", "title", "description", "is_public", "date_uploaded", "updated_at"]


def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _parse_bool(value: Optional[str], default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def sanitize_filename(original_name: str) -> str:
    base = os.path.basename(original_name)
    name, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file extension")
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    if not name:
        name = "document"
    return f"{name}{ext}"


@dataclass
class IndexRow:
    filename: str
    title: str
    description: str
    is_public: bool
    date_uploaded: str
    updated_at: str


class IndexStore:
    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)
        self.markdown_dir = self.base_path / "markdown_files"
        self.database_dir = self.base_path / "database"
        self.prompts_dir = self.base_path / "prompts"
        self.index_path = self.database_dir / "index.csv"
        self.lock_path = self.database_dir / "index.csv.lock"

    def ensure_directories(self) -> None:
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_rows([])

    def list_rows(self) -> List[IndexRow]:
        with FileLock(str(self.lock_path)):
            rows = self._read_rows()
        return rows

    def get_row(self, filename: str) -> Optional[IndexRow]:
        with FileLock(str(self.lock_path)):
            rows = self._read_rows()
        for row in rows:
            if row.filename == filename:
                return row
        return None

    def upsert_row(self, row: IndexRow) -> None:
        with FileLock(str(self.lock_path)):
            rows = self._read_rows()
            updated = False
            for idx, existing in enumerate(rows):
                if existing.filename == row.filename:
                    rows[idx] = row
                    updated = True
                    break
            if not updated:
                rows.append(row)
            self._write_rows(rows)

    def delete_row(self, filename: str) -> None:
        with FileLock(str(self.lock_path)):
            rows = [row for row in self._read_rows() if row.filename != filename]
            self._write_rows(rows)

    def toggle_public(self, filename: str, is_public: bool) -> None:
        with FileLock(str(self.lock_path)):
            rows = self._read_rows()
            for row in rows:
                if row.filename == filename:
                    row.is_public = is_public
                    row.updated_at = _timestamp()
            self._write_rows(rows)

    def ensure_unique_filename(self, filename: str) -> str:
        path = self.markdown_dir / filename
        if not path.exists():
            return filename
        name, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = f"{name}-{counter}{ext}"
            if not (self.markdown_dir / candidate).exists():
                return candidate
            counter += 1

    def save_markdown_file(self, filename: str, content: bytes) -> str:
        sanitized = sanitize_filename(filename)
        unique_name = self.ensure_unique_filename(sanitized)
        path = self.markdown_dir / unique_name
        path.write_bytes(content)
        return unique_name

    def delete_markdown_file(self, filename: str) -> None:
        path = self.markdown_dir / filename
        if path.exists():
            path.unlink()

    def list_markdown_files(self) -> List[str]:
        files = []
        for entry in self.markdown_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in ALLOWED_EXTENSIONS:
                files.append(entry.name)
        return sorted(files)

    def build_row(
        self,
        filename: str,
        title: str,
        description: str,
        is_public: bool,
        date_uploaded: Optional[str] = None,
    ) -> IndexRow:
        return IndexRow(
            filename=filename,
            title=title or "",
            description=description or "",
            is_public=is_public,
            date_uploaded=date_uploaded or _today_str(),
            updated_at=_timestamp(),
        )

    def sync_new_files(self, default_public: bool) -> List[str]:
        files = self.list_markdown_files()
        with FileLock(str(self.lock_path)):
            rows = self._read_rows()
            existing = {row.filename for row in rows}
            new_files = [name for name in files if name not in existing]
            for name in new_files:
                rows.append(
                    self.build_row(
                        filename=name,
                        title="",
                        description="",
                        is_public=default_public,
                        date_uploaded=_today_str(),
                    )
                )
            self._write_rows(rows)
        return new_files

    def update_missing_metadata(self, updates: Dict[str, Dict[str, str]]) -> None:
        if not updates:
            return
        with FileLock(str(self.lock_path)):
            rows = self._read_rows()
            for row in rows:
                if row.filename in updates:
                    update = updates[row.filename]
                    if update.get("title"):
                        row.title = update["title"]
                    if update.get("description"):
                        row.description = update["description"]
                    row.updated_at = _timestamp()
            self._write_rows(rows)

    def _read_rows(self) -> List[IndexRow]:
        if not self.index_path.exists():
            return []
        with self.index_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows: List[IndexRow] = []
            for record in reader:
                filename = (record.get("filename") or "").strip()
                if not filename:
                    continue
                rows.append(
                    IndexRow(
                        filename=filename,
                        title=(record.get("title") or "").strip(),
                        description=(record.get("description") or "").strip(),
                        is_public=_parse_bool(record.get("is_public"), True),
                        date_uploaded=(record.get("date_uploaded") or _today_str()).strip(),
                        updated_at=(record.get("updated_at") or "").strip(),
                    )
                )
        return rows

    def _write_rows(self, rows: List[IndexRow]) -> None:
        self.database_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=self.database_dir,
            newline="",
            encoding="utf-8",
        ) as tmp_file:
            writer = csv.DictWriter(tmp_file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "filename": row.filename,
                        "title": row.title,
                        "description": row.description,
                        "is_public": _bool_str(row.is_public),
                        "date_uploaded": row.date_uploaded,
                        "updated_at": row.updated_at,
                    }
                )
        os.replace(tmp_file.name, self.index_path)
