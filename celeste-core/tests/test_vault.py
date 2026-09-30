import os
import time
from pathlib import Path

from app.config import Settings
from app.services.tools import ToolRouter, build_vault_index
from app.services.vault import VaultIndex, split_note


TOKEN = "vault-test-token"


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "Vault"
    (vault / "Honda Civic").mkdir(parents=True)
    (vault / "Honda Civic" / "04 - Mantenimiento.md").write_text(
        "---\ntipo: nota\n---\n# Mantenimiento\n\n## Aceite\n\n"
        "Cambiar el aceite del Civic cada 5000 km con 10W-30.\n\n"
        "## Frenos\n\nRevisar pastillas cada 20000 km.\n",
        encoding="utf-8",
    )
    (vault / "Embarazo").mkdir()
    (vault / "Embarazo" / "01 - Datos.md").write_text(
        "# Datos\n\nVerónica tiene control prenatal el 15 de octubre.\n", encoding="utf-8"
    )
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "workspace.md").write_text("aceite interno de obsidian", encoding="utf-8")
    brain = vault / "CelesteBrain"
    (brain / "notes").mkdir(parents=True)
    (brain / "notes" / "cruda.md").write_text("aceite nota cruda de Celeste", encoding="utf-8")
    return vault


def _configure(tmp_path: Path, monkeypatch, vault: Path) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(vault / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_VAULT_DIR", str(vault))
    monkeypatch.delenv("CELESTE_VAULT_EXCLUDE", raising=False)
    return Settings.from_env()


def test_split_note_uses_headings_and_drops_frontmatter():
    chunks = split_note(
        "Civic/x.md",
        "---\ntipo: a\n---\n# T\n\n## Aceite\n\n" + "a " * 150 + "\n\n## Frenos\n\n" + "b " * 150,
    )
    assert [c.heading for c in chunks] == ["Aceite", "Frenos"]
    assert all("tipo:" not in c.content for c in chunks)
    assert chunks[0].chunk_id == "Civic/x.md#0"


def test_split_note_splits_huge_sections_by_paragraph():
    body = "\n\n".join("párrafo " * 60 for _ in range(10))
    chunks = split_note("x.md", "# Grande\n\n" + body)
    assert len(chunks) > 1
    assert all(len(c.content) <= 1800 * 2 for c in chunks)


def test_search_vault_finds_curated_note_section(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, _vault(tmp_path))
    router = ToolRouter(settings)

    result = router.execute("search_vault", {"query": "cada cuanto cambio el aceite del civic"})

    assert result.status == "executed"
    top = result.output[0]
    assert top["path"] == "Honda Civic/04 - Mantenimiento.md"
    assert top["section"] == "Aceite"
    assert "5000 km" in top["text"]
    assert top["source"] == "vault"


def test_search_vault_skips_hidden_folders_and_celeste_brain(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, _vault(tmp_path))

    results = ToolRouter(settings).execute("search_vault", {"query": "aceite", "limit": 8}).output

    paths = {r["path"] for r in results}
    assert not any(p.startswith(".obsidian") or p.startswith("CelesteBrain") for p in paths)


def test_search_vault_respects_exclude_list(tmp_path, monkeypatch):
    vault = _vault(tmp_path)
    settings = _configure(tmp_path, monkeypatch, vault)
    monkeypatch.setenv("CELESTE_VAULT_EXCLUDE", "Embarazo")
    settings = Settings.from_env()

    results = ToolRouter(settings).execute("search_vault", {"query": "Verónica prenatal"}).output

    assert results == []


def test_vault_index_picks_up_edits_and_deletions(tmp_path, monkeypatch):
    vault = _vault(tmp_path)
    settings = _configure(tmp_path, monkeypatch, vault)
    index = build_vault_index(settings)
    assert index.search("pastillas")

    note = vault / "Honda Civic" / "04 - Mantenimiento.md"
    note.write_text("# Mantenimiento\n\nAhora uso aceite sintético 5W-30.\n", encoding="utf-8")
    future = time.time() + 5
    os.utime(note, (future, future))
    index.refresh()  # en producción pasa solo, a lo sumo 15 s después
    assert index.search("pastillas") == []
    assert index.search("sintético")[0]["path"] == "Honda Civic/04 - Mantenimiento.md"

    note.unlink()
    index.refresh()
    assert index.search("sintético") == []


def test_search_vault_is_read_only(tmp_path, monkeypatch):
    vault = _vault(tmp_path)
    settings = _configure(tmp_path, monkeypatch, vault)
    before = {p: p.read_bytes() for p in vault.rglob("*.md")}

    ToolRouter(settings).execute("search_vault", {"query": "aceite"})

    assert {p: p.read_bytes() for p in vault.rglob("*.md")} == before


def test_search_vault_not_registered_without_vault_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.delenv("CELESTE_VAULT_DIR", raising=False)

    assert not ToolRouter(Settings.from_env()).has_tool("search_vault")


def test_vault_index_semantic_layer_is_optional(tmp_path):
    vault = _vault(tmp_path)
    index = VaultIndex(vault, tmp_path / "idx", embedder=None)
    assert index.sync_embeddings() == 0
    # Secciones cortas se fusionan con la anterior: "Frenos" vive dentro del bloque de "Aceite".
    assert "pastillas" in index.search("frenos")[0]["text"]
