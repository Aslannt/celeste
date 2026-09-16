from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import Note
from app.services.embeddings import EmbeddingError
from app.services.index import BrainIndex, _content_hash


def _note(
    note_id: str,
    title: str,
    content: str,
    *,
    tags: list[str] | None = None,
    deleted: bool = False,
) -> Note:
    return Note(
        id=note_id,
        title=title,
        content=content,
        type="note",
        tags=tags or [],
        created_at="2026-09-16T00:00:00Z",
        updated_at="2026-09-16T00:00:00Z",
        version=1,
        deleted=deleted,
    )


class FakeEmbedder:
    """Deterministic fake: returns a caller-provided vector per text, keyed by
    substring match, so tests can control similarity without a real model."""

    def __init__(self, vectors_by_keyword: dict[str, list[float]], default: list[float] | None = None):
        self.model = "fake-embedder"
        self.vectors_by_keyword = vectors_by_keyword
        self.default = default or [0.0, 0.0]
        self.calls: list[list[str]] = []
        self.fail = False

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.fail:
            raise EmbeddingError("embedding backend unavailable")
        vectors = []
        for text in texts:
            vector = self.default
            for keyword, candidate in self.vectors_by_keyword.items():
                if keyword in text:
                    vector = candidate
                    break
            vectors.append(vector)
        return vectors


def _embedding_rows(db_path: Path) -> dict[str, str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT note_id, content_hash FROM notes_embeddings").fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        connection.close()


def test_search_ids_is_keyword_only_without_embedder(tmp_path):
    index = BrainIndex(tmp_path / "brain")
    index.rebuild([_note("n1", "Cambio de aceite", "Revisar aceite de la moto")])

    assert index.search_ids("aceite moto") == ["n1"]
    assert index.search_ids("algo que no comparte ninguna palabra") == []


def test_upsert_stores_embedding_and_skips_unchanged_recompute(tmp_path):
    embedder = FakeEmbedder({"banco": [1.0, 0.0]})
    index = BrainIndex(tmp_path / "brain", embedder=embedder)
    note = _note("n1", "El tipo del banco", "Hablamos del banco el jueves")

    index.upsert(note)
    assert len(embedder.calls) == 1
    assert _embedding_rows(index.db_path) == {"n1": _content_hash(note)}

    # Re-upserting the exact same content must not call the embedder again.
    index.upsert(note)
    assert len(embedder.calls) == 1


def test_upsert_removes_embedding_when_note_deleted(tmp_path):
    embedder = FakeEmbedder({"banco": [1.0, 0.0]})
    index = BrainIndex(tmp_path / "brain", embedder=embedder)
    note = _note("n1", "El tipo del banco", "Hablamos del banco el jueves")
    index.upsert(note)
    assert _embedding_rows(index.db_path)

    deleted = note.model_copy(update={"deleted": True})
    index.upsert(deleted)
    assert _embedding_rows(index.db_path) == {}


def test_rebuild_batches_embedding_calls_and_prunes_stale(tmp_path):
    embedder = FakeEmbedder({})
    index = BrainIndex(tmp_path / "brain", embedder=embedder)
    notes = [
        _note("n1", "Nota uno", "Contenido uno"),
        _note("n2", "Nota dos", "Contenido dos"),
    ]
    index.rebuild(notes)

    assert len(embedder.calls) == 1  # one batched call, not one per note
    assert len(embedder.calls[0]) == 2
    assert set(_embedding_rows(index.db_path)) == {"n1", "n2"}

    # Rebuilding with only n1 present must prune n2's embedding.
    index.rebuild([notes[0]])
    assert set(_embedding_rows(index.db_path)) == {"n1"}
    # n1's content did not change, so it should not be re-embedded.
    assert len(embedder.calls) == 1


def test_semantic_search_finds_notes_with_no_shared_keywords(tmp_path):
    embedder = FakeEmbedder(
        {
            "prestamo hipotecario": [1.0, 0.0],
            "receta de pasta": [0.0, 1.0],
        },
        default=[0.9, 0.1],  # the query below will land close to the bank note
    )
    index = BrainIndex(tmp_path / "brain", embedder=embedder)
    index.rebuild(
        [
            _note("bank", "Reunion con Carlos", "Hablamos del prestamo hipotecario del apartamento"),
            _note("food", "Cena del viernes", "Probamos una receta de pasta nueva"),
        ]
    )

    # Query shares zero keywords with either note, so FTS5 alone would return nothing.
    results = index.search_ids("que era lo del tipo del banco")

    assert results
    assert results[0] == "bank"


def test_semantic_search_degrades_gracefully_when_embedder_fails(tmp_path):
    embedder = FakeEmbedder({"aceite": [1.0, 0.0]})
    index = BrainIndex(tmp_path / "brain", embedder=embedder)
    index.rebuild([_note("n1", "Cambio de aceite", "Revisar aceite de la moto")])

    embedder.fail = True
    # Keyword match still works even though every embedding call now fails.
    assert index.search_ids("aceite moto") == ["n1"]
