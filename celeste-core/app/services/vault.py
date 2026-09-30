"""Read-only index over the user's whole Obsidian vault (ADR-014).

Celeste Brain (``CELESTE_BRAIN_DIR``) stays the only place Celeste *writes*.
This module lets her *read* the rest of the vault - the curated notes the user
keeps by hand - so questions like "cada cuanto le cambio el aceite al Civic"
can be answered from the user's own notes before falling back to the web.

Like the Brain index, this is a rebuildable cache: Markdown is the source of
truth, the SQLite file can be deleted at any time. Notes are split into
heading-sized chunks so the model receives only the relevant section, not a
whole archive note, which keeps each answer cheap.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.services.embeddings import EmbeddingError, OllamaEmbeddingClient
from app.services.index import (
    BrainIndex,
    _cosine_similarity,
    _pack_vector,
    _reciprocal_rank_fusion,
    _unpack_vector,
)

_VAULT_LOCK = threading.RLock()
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$", re.MULTILINE)
_MAX_CHUNK_CHARS = 1800
_MIN_CHUNK_CHARS = 200
_SNIPPET_CHARS = 1200
_EMBED_RE = re.compile(r"^\s*!\[\[[^\]]*\]\]\s*$", re.MULTILINE)
# Raw material (pasted chats, assistant logs) ranks after curated notes: it is
# still searchable, but a curated answer should win when both match.
_RAW_MARKERS = ("conversaciones raw/", "copilot/", "celestebrain/")
_REFRESH_EVERY_SECONDS = 15.0
# Spoken questions carry words that never appear in the answer ("cuánto pago de
# arriendo"): drop them so the strict AND query can still hit curated notes.
_QUESTION_WORDS = frozenset(
    "cuanto cuanta cuantos cuantas cuando como donde cual cuales quien quienes que "
    "dime sabes tengo tienes hay es son esta estan".split()
)
_last_refresh: dict[str, float] = {}

try:  # optional: ~50x faster cosine over thousands of sections
    import numpy as _np
except ImportError:  # pragma: no cover - pure Python fallback below
    _np = None
_matrix_cache: dict[str, tuple[float, list[str], object]] = {}


@dataclass(frozen=True)
class VaultChunk:
    chunk_id: str
    path: str
    title: str
    heading: str
    content: str

    @property
    def embedding_text(self) -> str:
        return f"{self.title} {self.heading}\n{self.content}".strip()

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.embedding_text.encode("utf-8")).hexdigest()


def split_note(relative_path: str, text: str) -> list[VaultChunk]:
    """Split a Markdown note into heading-sized chunks (frontmatter removed)."""
    title = Path(relative_path).stem
    body = _FRONTMATTER_RE.sub("", text, count=1)
    body = _EMBED_RE.sub("", body).strip()  # image/file embeds are noise for search
    if not body:
        return []

    sections: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(body))
    if not matches or matches[0].start() > 0:
        end = matches[0].start() if matches else len(body)
        sections.append(("", body[:end]))
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(body)
        sections.append((match.group(2).strip(), body[match.end():end]))

    # Merge tiny sections into the previous one, split huge ones by paragraph.
    merged: list[tuple[str, str]] = []
    for heading, content in sections:
        content = content.strip()
        if not content:
            continue
        if merged and len(content) < _MIN_CHUNK_CHARS and len(merged[-1][1]) < _MAX_CHUNK_CHARS:
            prev_heading, prev_content = merged[-1]
            label = f"{heading}\n" if heading else ""
            merged[-1] = (prev_heading, f"{prev_content}\n\n{label}{content}")
            continue
        merged.append((heading, content))

    chunks: list[VaultChunk] = []
    for heading, content in merged:
        pieces: list[str] = []
        current = ""
        for paragraph in re.split(r"\n\s*\n", content):
            if current and len(current) + len(paragraph) > _MAX_CHUNK_CHARS:
                pieces.append(current)
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            pieces.append(current)
        for piece in pieces:
            chunks.append(
                VaultChunk(
                    chunk_id=f"{relative_path}#{len(chunks)}",
                    path=relative_path,
                    title=title,
                    heading=heading,
                    content=piece.strip()[: _MAX_CHUNK_CHARS * 2],
                )
            )
    return chunks


class VaultIndex:
    def __init__(
        self,
        vault_dir: Path,
        index_dir: Path,
        excluded: tuple[str, ...] = (),
        embedder: OllamaEmbeddingClient | None = None,
    ):
        self.vault_dir = vault_dir
        self.db_path = index_dir / "vault-index.sqlite3"
        self.excluded = tuple(part.strip().strip("/\\").casefold() for part in excluded if part.strip())
        self.embedder = embedder

    # ---------- storage ----------
    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS vault_files (
                path TEXT PRIMARY KEY, mtime REAL NOT NULL, size INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
                chunk_id UNINDEXED, path UNINDEXED, title, heading, content
            );
            CREATE TABLE IF NOT EXISTS vault_embeddings (
                chunk_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL,
                model TEXT NOT NULL, vector BLOB NOT NULL
            );
            """
        )
        return connection

    def _is_excluded(self, relative: Path) -> bool:
        parts = relative.parts
        if any(part.startswith(".") for part in parts):
            return True
        normalized = "/".join(parts).casefold()
        return any(normalized == ex or normalized.startswith(ex + "/") for ex in self.excluded)

    def _scan(self) -> dict[str, tuple[float, int]]:
        found: dict[str, tuple[float, int]] = {}
        if not self.vault_dir.is_dir():
            return found
        for path in self.vault_dir.rglob("*.md"):
            relative = path.relative_to(self.vault_dir)
            if self._is_excluded(relative):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            found[relative.as_posix()] = (stat.st_mtime, stat.st_size)
        return found

    # ---------- refresh ----------
    def refresh(self) -> int:
        """Reindex only files that changed since last time. Returns files touched."""
        current = self._scan()
        with _VAULT_LOCK:
            connection = self._connect()
            try:
                known = {
                    row["path"]: (row["mtime"], row["size"])
                    for row in connection.execute("SELECT path, mtime, size FROM vault_files")
                }
                removed = set(known) - set(current)
                changed = [p for p, meta in current.items() if known.get(p) != meta]
                for relative in list(removed) + changed:
                    connection.execute("DELETE FROM vault_fts WHERE path = ?", (relative,))
                    connection.execute("DELETE FROM vault_embeddings WHERE chunk_id LIKE ?", (relative + "#%",))
                    connection.execute("DELETE FROM vault_files WHERE path = ?", (relative,))
                for relative in changed:
                    try:
                        text = (self.vault_dir / relative).read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    connection.executemany(
                        "INSERT INTO vault_fts(chunk_id, path, title, heading, content) VALUES (?, ?, ?, ?, ?)",
                        [(c.chunk_id, c.path, c.title, c.heading, c.content) for c in split_note(relative, text)],
                    )
                    mtime, size = current[relative]
                    connection.execute(
                        "INSERT INTO vault_files(path, mtime, size) VALUES (?, ?, ?)", (relative, mtime, size)
                    )
                connection.commit()
                return len(removed) + len(changed)
            except sqlite3.Error as exc:
                connection.rollback()
                print(f"[Celeste] WARNING: vault index refresh failed: {exc}")
                return 0
            finally:
                connection.close()

    def sync_embeddings(self) -> int:
        """Embed chunks that have no (or a stale) vector. Best effort, never raises."""
        if self.embedder is None:
            return 0
        with _VAULT_LOCK:
            connection = self._connect()
            try:
                rows = connection.execute("SELECT chunk_id, path, title, heading, content FROM vault_fts").fetchall()
                existing = {
                    row["chunk_id"]: row["content_hash"]
                    for row in connection.execute("SELECT chunk_id, content_hash FROM vault_embeddings")
                }
            finally:
                connection.close()
        chunks = [VaultChunk(r["chunk_id"], r["path"], r["title"], r["heading"], r["content"]) for r in rows]
        pending = [c for c in chunks if existing.get(c.chunk_id) != c.content_hash]
        if not pending:
            return 0
        # Background batches may wait for Ollama to load the model: give them a
        # long timeout. Query-time embeddings keep the short one (never block an answer).
        batch_embedder = OllamaEmbeddingClient(
            str(self.embedder.client.base_url), self.embedder.model, timeout_seconds=120.0
        )
        done = 0
        for start in range(0, len(pending), 32):
            batch = pending[start:start + 32]
            try:
                vectors = batch_embedder.embed([c.embedding_text for c in batch])
            except EmbeddingError as exc:
                print(f"[Celeste] WARNING: vault embeddings paused: {exc}")
                break
            with _VAULT_LOCK:
                connection = self._connect()
                try:
                    connection.executemany(
                        """
                        INSERT INTO vault_embeddings(chunk_id, content_hash, model, vector) VALUES (?, ?, ?, ?)
                        ON CONFLICT(chunk_id) DO UPDATE SET content_hash = excluded.content_hash,
                            model = excluded.model, vector = excluded.vector
                        """,
                        [(c.chunk_id, c.content_hash, self.embedder.model, _pack_vector(v)) for c, v in zip(batch, vectors)],
                    )
                    connection.commit()
                    done += len(batch)
                finally:
                    connection.close()
        return done

    # ---------- search ----------
    @staticmethod
    def _strip_question_words(query: str) -> str:
        def plain(word: str) -> str:
            return "".join(c for c in unicodedata.normalize("NFKD", word.casefold()) if not unicodedata.combining(c))

        kept = [w for w in re.findall(r"[^\W_]+", query) if plain(w) not in _QUESTION_WORDS]
        return " ".join(kept) or query

    def _keyword_ids(self, connection: sqlite3.Connection, query: str, limit: int) -> list[str]:
        query = self._strip_question_words(query)
        for match_all in (True, False):
            fts_query = BrainIndex._fts_query(query, match_all=match_all)
            if not fts_query:
                return []
            rows = connection.execute(
                "SELECT chunk_id FROM vault_fts WHERE vault_fts MATCH ? ORDER BY bm25(vault_fts, 0, 0, 4.0, 2.0, 1.0) LIMIT ?",
                (fts_query, limit),
            ).fetchall()
            if rows:
                return [row["chunk_id"] for row in rows]
        return []

    def _semantic_ids(self, connection: sqlite3.Connection, query: str, limit: int) -> list[str]:
        if self.embedder is None:
            return []
        if _np is not None:
            return self._semantic_ids_numpy(connection, query, limit)
        rows = connection.execute("SELECT chunk_id, vector FROM vault_embeddings").fetchall()
        if not rows:
            return []
        try:
            [query_vector] = self.embedder.embed([query])
        except EmbeddingError:
            return []
        scored = sorted(
            ((_cosine_similarity(query_vector, _unpack_vector(r["vector"])), r["chunk_id"]) for r in rows),
            reverse=True,
        )
        return [chunk_id for _, chunk_id in scored[:limit]]

    def _semantic_ids_numpy(self, connection: sqlite3.Connection, query: str, limit: int) -> list[str]:
        key = str(self.db_path)
        version = connection.execute("SELECT count(*), coalesce(sum(length(content_hash)), 0) FROM vault_embeddings").fetchone()
        stamp = float(version[0]) * 1e9 + float(version[1])
        cached = _matrix_cache.get(key)
        if cached is None or cached[0] != stamp:
            rows = connection.execute("SELECT chunk_id, vector FROM vault_embeddings").fetchall()
            if not rows:
                return []
            ids = [r["chunk_id"] for r in rows]
            matrix = _np.frombuffer(b"".join(r["vector"] for r in rows), dtype="<f4").reshape(len(rows), -1)
            matrix = matrix / (_np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
            cached = (stamp, ids, matrix)
            _matrix_cache[key] = cached
        _, ids, matrix = cached
        try:
            [query_vector] = self.embedder.embed([query])
        except EmbeddingError:
            return []
        q = _np.asarray(query_vector, dtype="float32")
        scores = matrix @ (q / (_np.linalg.norm(q) + 1e-9))
        top = _np.argsort(-scores)[:limit]
        return [ids[i] for i in top]

    def refresh_if_stale(self) -> None:
        key = str(self.db_path)
        now = time.monotonic()
        if now - _last_refresh.get(key, -1e9) >= _REFRESH_EVERY_SECONDS:
            self.refresh()
            _last_refresh[key] = now

    def search(self, query: str, limit: int = 4) -> list[dict[str, str]]:
        self.refresh_if_stale()
        pool = max(limit * 3, 12)
        with _VAULT_LOCK:
            connection = self._connect()
            try:
                keyword = self._keyword_ids(connection, query, pool)
                semantic = self._semantic_ids(connection, query, pool)
                if keyword and semantic:
                    ranked = _reciprocal_rank_fusion([keyword, semantic])
                else:
                    ranked = keyword or semantic
                ranked = sorted(ranked, key=lambda cid: any(m in cid.casefold() for m in _RAW_MARKERS))
                results = []
                for chunk_id in ranked[:limit]:
                    row = connection.execute(
                        "SELECT path, title, heading, content FROM vault_fts WHERE chunk_id = ?", (chunk_id,)
                    ).fetchone()
                    if row is None:
                        continue
                    results.append(
                        {
                            "source": "vault",
                            "path": row["path"],
                            "note": row["title"],
                            "section": row["heading"],
                            "text": row["content"][:_SNIPPET_CHARS],
                        }
                    )
                return results
            except sqlite3.Error as exc:
                print(f"[Celeste] WARNING: vault search failed: {exc}")
                return []
            finally:
                connection.close()
