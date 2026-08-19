from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

from app.models import Note

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


class BrainIndex:
    """Rebuildable SQLite/FTS5 index for Markdown notes.

    Markdown remains the source of truth. This database may be deleted at any
    time and rebuilt from CelesteBrain/notes.
    """

    def __init__(self, brain_dir: Path):
        self.brain_dir = brain_dir
        self.index_dir = brain_dir / ".celeste"
        self.db_path = self.index_dir / "brain-index.sqlite3"

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
                connection.commit()
            except sqlite3.Error as exc:
                raise BrainIndexError(f"No se pudo inicializar FTS5: {exc}") from exc
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
                return len(active_notes)
            except sqlite3.Error as exc:
                connection.rollback()
                raise BrainIndexError(f"No se pudo reconstruir el indice: {exc}") from exc
            finally:
                connection.close()

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
        # become raw FTS5 syntax. Prefer strict AND for precision; search_ids may
        # retry with OR only when the strict natural-language query has no hits.
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

    def search_ids(self, query: str, limit: int = 20) -> list[str]:
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
