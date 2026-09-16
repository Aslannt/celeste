from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
import threading
from pathlib import Path

from app.models import Note
from app.services.embeddings import EmbeddingError, OllamaEmbeddingClient

_INDEX_LOCK = threading.RLock()
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_SEARCH_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "algo",
        "ante",
        "con",
        "contra",
        "de",
        "del",
        "desde",
        "donde",
        "el",
        "ella",
        "ellos",
        "en",
        "entre",
        "era",
        "es",
        "esa",
        "ese",
        "eso",
        "esta",
        "este",
        "esto",
        "ha",
        "habia",
        "hasta",
        "hay",
        "la",
        "las",
        "lo",
        "los",
        "me",
        "mi",
        "mis",
        "no",
        "nos",
        "o",
        "para",
        "pero",
        "por",
        "que",
        "se",
        "si",
        "sin",
        "sobre",
        "su",
        "sus",
        "te",
        "tenia",
        "tengo",
        "tu",
        "tus",
        "un",
        "una",
        "unas",
        "uno",
        "unos",
        "y",
        "ya",
    }
)


class BrainIndexError(RuntimeError):
    pass


def _embedding_text(note: Note) -> str:
    tag_text = " ".join(note.tags)
    return f"{note.title}\n{note.content}\n{tag_text}".strip()


def _content_hash(note: Note) -> str:
    return hashlib.sha256(_embedding_text(note).encode("utf-8")).hexdigest()


def _pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack_vector(blob: bytes) -> list[float]:
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[str]:
    """Combine ranked id lists by position, not by raw score.

    FTS5's bm25 and cosine similarity live on incomparable scales, so fusing by
    rank position (RRF) avoids inventing a weighting between them. k=60 is the
    standard constant from the original RRF paper; it has no reason to be tuned
    for a personal-scale index.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for position, note_id in enumerate(ranked):
            scores[note_id] = scores.get(note_id, 0.0) + 1.0 / (k + position + 1)
    return [note_id for note_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


class BrainIndex:
    """Rebuildable SQLite/FTS5 + semantic index for Markdown notes.

    Markdown remains the source of truth. This database may be deleted at any
    time and rebuilt from CelesteBrain/notes. Embeddings are an optional layer
    on top of the same reconstructible file: if the embedder is unavailable
    (disabled, or Ollama/the embedding model isn't reachable), search silently
    degrades to keyword-only FTS5, exactly like before this feature existed.
    """

    def __init__(self, brain_dir: Path, embedder: OllamaEmbeddingClient | None = None):
        self.brain_dir = brain_dir
        self.index_dir = brain_dir / ".celeste"
        self.db_path = self.index_dir / "brain-index.sqlite3"
        self.embedder = embedder

    def _connect(self) -> sqlite3.Connection:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with _INDEX_LOCK:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                        note_id UNINDEXED,
                        title,
                        content,
                        tags,
                        note_type UNINDEXED,
                        updated_at UNINDEXED
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notes_embeddings (
                        note_id TEXT PRIMARY KEY,
                        content_hash TEXT NOT NULL,
                        model TEXT NOT NULL,
                        vector BLOB NOT NULL
                    )
                    """
                )
                connection.commit()
            except sqlite3.Error as exc:
                raise BrainIndexError(f"No se pudo inicializar el indice: {exc}") from exc
            finally:
                connection.close()

    @staticmethod
    def _row(note: Note) -> tuple[str, str, str, str, str, str]:
        return (
            note.id,
            note.title,
            note.content,
            " ".join(note.tags),
            note.type,
            note.updated_at,
        )

    def rebuild(self, notes: list[Note]) -> int:
        active_notes = [note for note in notes if not note.deleted]
        with _INDEX_LOCK:
            self.initialize()
            connection = self._connect()
            try:
                connection.execute("DELETE FROM notes_fts")
                connection.executemany(
                    """
                    INSERT INTO notes_fts(note_id, title, content, tags, note_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [self._row(note) for note in active_notes],
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise BrainIndexError(f"No se pudo reconstruir el indice: {exc}") from exc
            finally:
                connection.close()

        self._sync_embeddings_full(active_notes)
        return len(active_notes)

    def upsert(self, note: Note) -> None:
        with _INDEX_LOCK:
            self.initialize()
            connection = self._connect()
            try:
                connection.execute("DELETE FROM notes_fts WHERE note_id = ?", (note.id,))
                if not note.deleted:
                    connection.execute(
                        """
                        INSERT INTO notes_fts(note_id, title, content, tags, note_type, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        self._row(note),
                    )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise BrainIndexError(f"No se pudo actualizar el indice: {exc}") from exc
            finally:
                connection.close()

        self._sync_embedding_one(note)

    # ---------- Embeddings (best-effort, never fails a note write) ----------

    def _sync_embedding_one(self, note: Note) -> None:
        if self.embedder is None:
            return
        with _INDEX_LOCK:
            connection = self._connect()
            try:
                if note.deleted:
                    connection.execute("DELETE FROM notes_embeddings WHERE note_id = ?", (note.id,))
                    connection.commit()
                    return

                new_hash = _content_hash(note)
                existing = connection.execute(
                    "SELECT content_hash FROM notes_embeddings WHERE note_id = ?",
                    (note.id,),
                ).fetchone()
                if existing is not None and existing["content_hash"] == new_hash:
                    return

                try:
                    [vector] = self.embedder.embed([_embedding_text(note)])
                except EmbeddingError as exc:
                    print(f"[Celeste] WARNING: embedding update skipped for note {note.id}: {exc}")
                    return

                connection.execute(
                    """
                    INSERT INTO notes_embeddings(note_id, content_hash, model, vector)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(note_id) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        model = excluded.model,
                        vector = excluded.vector
                    """,
                    (note.id, new_hash, self.embedder.model, _pack_vector(vector)),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                print(f"[Celeste] WARNING: embedding sync failed for note {note.id}: {exc}")
            finally:
                connection.close()

    def _sync_embeddings_full(self, notes: list[Note]) -> None:
        if self.embedder is None:
            return
        with _INDEX_LOCK:
            connection = self._connect()
            try:
                active_ids = {note.id for note in notes}
                existing = {
                    row["note_id"]: row["content_hash"]
                    for row in connection.execute(
                        "SELECT note_id, content_hash FROM notes_embeddings"
                    ).fetchall()
                }

                stale_ids = set(existing) - active_ids
                if stale_ids:
                    connection.executemany(
                        "DELETE FROM notes_embeddings WHERE note_id = ?",
                        [(note_id,) for note_id in stale_ids],
                    )
                    connection.commit()

                to_embed = [note for note in notes if existing.get(note.id) != _content_hash(note)]
                if not to_embed:
                    return

                try:
                    vectors = self.embedder.embed([_embedding_text(note) for note in to_embed])
                except EmbeddingError as exc:
                    print(f"[Celeste] WARNING: embedding rebuild skipped: {exc}")
                    return

                connection.executemany(
                    """
                    INSERT INTO notes_embeddings(note_id, content_hash, model, vector)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(note_id) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        model = excluded.model,
                        vector = excluded.vector
                    """,
                    [
                        (note.id, _content_hash(note), self.embedder.model, _pack_vector(vector))
                        for note, vector in zip(to_embed, vectors)
                    ],
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                print(f"[Celeste] WARNING: embedding rebuild failed: {exc}")
            finally:
                connection.close()

    # ---------- Search ----------

    @staticmethod
    def _search_tokens(value: str) -> list[str]:
        tokens = list(dict.fromkeys(_TOKEN_RE.findall(value.casefold())))
        if not tokens:
            return []
        significant = [token for token in tokens if token not in _SEARCH_STOPWORDS]
        return significant or tokens

    @classmethod
    def _fts_query(cls, value: str, *, match_all: bool = True) -> str | None:
        tokens = cls._search_tokens(value)
        if not tokens:
            return None
        # Tokens are always quoted, so punctuation or model-generated text cannot
        # become raw FTS5 syntax. Prefer strict AND for precision; the keyword
        # search may retry with OR only when the strict query has no hits.
        joiner = " AND " if match_all else " OR "
        return joiner.join(f'"{token}"' for token in tokens)

    @staticmethod
    def _search_rows(
        connection: sqlite3.Connection,
        fts_query: str,
        limit: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """
            SELECT note_id
            FROM notes_fts
            WHERE notes_fts MATCH ?
            ORDER BY bm25(notes_fts), updated_at DESC
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

    def _keyword_search_ids(self, query: str, limit: int) -> list[str]:
        strict_query = self._fts_query(query, match_all=True)
        if not strict_query:
            return []

        with _INDEX_LOCK:
            self.initialize()
            connection = self._connect()
            try:
                rows = self._search_rows(connection, strict_query, limit)
                if not rows and " AND " in strict_query:
                    relaxed_query = self._fts_query(query, match_all=False)
                    if relaxed_query and relaxed_query != strict_query:
                        rows = self._search_rows(connection, relaxed_query, limit)
                return [str(row["note_id"]) for row in rows]
            except sqlite3.Error as exc:
                raise BrainIndexError(f"No se pudo buscar en el indice: {exc}") from exc
            finally:
                connection.close()

    def _semantic_search_ids(self, query: str, limit: int) -> list[str]:
        if self.embedder is None:
            return []
        try:
            [query_vector] = self.embedder.embed([query])
        except EmbeddingError:
            return []

        with _INDEX_LOCK:
            self.initialize()
            connection = self._connect()
            try:
                rows = connection.execute("SELECT note_id, vector FROM notes_embeddings").fetchall()
            except sqlite3.Error:
                return []
            finally:
                connection.close()

        scored = [
            (_cosine_similarity(query_vector, _unpack_vector(row["vector"])), row["note_id"])
            for row in rows
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [note_id for _, note_id in scored[:limit]]

    def search_ids(self, query: str, limit: int = 20) -> list[str]:
        pool = max(limit * 3, 15)
        keyword_ids = self._keyword_search_ids(query, limit=pool)
        semantic_ids = self._semantic_search_ids(query, limit=pool)

        if not semantic_ids:
            return keyword_ids[:limit]
        if not keyword_ids:
            return semantic_ids[:limit]
        return _reciprocal_rank_fusion([keyword_ids, semantic_ids])[:limit]
