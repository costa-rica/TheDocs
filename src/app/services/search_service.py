import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from elasticsearch import Elasticsearch
from loguru import logger


@dataclass
class SearchResult:
    snippet: str
    filename: str


class SearchService:
    def __init__(
        self,
        url: Optional[str],
        index_name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self.index_name = index_name
        self._index_ready = False
        self.client: Optional[Elasticsearch] = None

        if url:
            kwargs = {}
            if username and password:
                kwargs["basic_auth"] = (username, password)
            self.client = Elasticsearch(url, **kwargs)

    def is_enabled(self) -> bool:
        return self.client is not None

    def ensure_index(self) -> None:
        if not self.client or self._index_ready:
            return
        try:
            exists = self.client.indices.exists(index=self.index_name)
            if not exists:
                self.client.indices.create(
                    index=self.index_name,
                    mappings={
                        "properties": {
                            "filename": {"type": "keyword"},
                            "content": {"type": "text"},
                            "is_public": {"type": "boolean"},
                        }
                    },
                )
            self._index_ready = True
        except Exception as exc:  # pragma: no cover - network
            logger.warning(f"Elasticsearch index check failed: {exc}")

    def index_document(self, filename: str, content: str, is_public: bool) -> None:
        if not self.client:
            return
        self.ensure_index()
        try:
            self.client.index(
                index=self.index_name,
                id=filename,
                document={
                    "filename": filename,
                    "content": content,
                    "is_public": is_public,
                },
                refresh=True,
            )
        except Exception as exc:  # pragma: no cover - network
            logger.warning(f"Elasticsearch index failed for {filename}: {exc}")

    def delete_document(self, filename: str) -> None:
        if not self.client:
            return
        self.ensure_index()
        try:
            self.client.delete(index=self.index_name, id=filename, ignore=[404], refresh=True)
        except Exception as exc:  # pragma: no cover - network
            logger.warning(f"Elasticsearch delete failed for {filename}: {exc}")

    def update_visibility(self, filename: str, is_public: bool) -> None:
        if not self.client:
            return
        self.ensure_index()
        try:
            self.client.update(
                index=self.index_name,
                id=filename,
                doc={"is_public": is_public},
                refresh=True,
            )
        except Exception as exc:  # pragma: no cover - network
            logger.warning(f"Elasticsearch update failed for {filename}: {exc}")

    def search(self, query: str, public_only: bool, size: int = 25) -> Optional[List[SearchResult]]:
        if not self.client:
            return None
        self.ensure_index()

        query = query.strip()
        if not query:
            return []

        search_query = _build_query(query)
        bool_query: Dict[str, List[Dict]] = {"must": [search_query]}
        if public_only:
            bool_query["filter"] = [{"term": {"is_public": True}}]

        body = {
            "query": {"bool": bool_query},
            "highlight": {
                "fields": {"content": {"fragment_size": 50, "number_of_fragments": 5}},
                "pre_tags": [""],
                "post_tags": [""],
            },
            "size": size,
        }

        try:
            response = self.client.search(index=self.index_name, body=body)
        except Exception as exc:  # pragma: no cover - network
            logger.warning(f"Elasticsearch search failed: {exc}")
            return None

        results: List[SearchResult] = []
        hits = response.get("hits", {}).get("hits", [])
        for hit in hits:
            source = hit.get("_source", {})
            filename = source.get("filename", "")
            fragments = hit.get("highlight", {}).get("content", [])
            if fragments:
                for fragment in fragments:
                    results.append(SearchResult(snippet=fragment, filename=filename))
            else:
                results.append(SearchResult(snippet="", filename=filename))
        return results


def _build_query(query: str) -> Dict:
    phrases = re.findall(r"\"([^\"]+)\"", query)
    if phrases:
        phrase = phrases[0].strip()
        return {"match_phrase": {"content": phrase}}

    terms = query.split()
    escaped = [f"*{_escape_query_string(term)}*" for term in terms if term]
    joined = " ".join(escaped)
    return {
        "query_string": {
            "query": joined,
            "fields": ["content"],
            "default_operator": "AND",
            "case_insensitive": True,
        }
    }


def _escape_query_string(value: str) -> str:
    return re.sub(r"([+\-=&|><!(){}\[\]^\"~:/\\])", r"\\\1", value)
