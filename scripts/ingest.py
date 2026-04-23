"""
Ingest script for CDM RAG chatbot.
"""

import sys
from pathlib import Path

# Allow running from repo root or scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ingestion.chunker import build_chunks
from app.ingestion.embedder import embed_documents
from app.ingestion.fetcher import list_entity_filenames, load_entity, load_manifest
from app.ingestion.graph_builder import build_graph
from app.ingestion.parser import parse_entity_file, parse_manifest
from app.retrieval.vector import upsert_chunks


def run():
    print("── Step 1: Loading manifest ──────────────────────────────")
    manifest_raw = load_manifest()
    manifest = parse_manifest(manifest_raw)
    filenames = list_entity_filenames(manifest_raw)
    print(f"  Found {len(filenames)} entity files in manifest.")

    print("\n── Step 2: Parsing entity files ──────────────────────────")
    entities: list[dict] = []
    skipped: list[str] = []
    for filename in filenames:
        raw = load_entity(filename)
        if raw is None:
            skipped.append(filename)
            continue
        # parse_entity_file expects a Path; write raw dict to a temp-like parse
        # We call the internal logic directly via a small helper below
        parsed = _parse_raw(raw, filename)
        if parsed:
            entities.append(parsed)
            print(f"  ✓ {parsed['entity_name']}  ({len(parsed['attributes'])} attrs, "
                  f"{len(parsed['relationships'])} rels)")
        else:
            skipped.append(filename)

    if skipped:
        print(f"  Skipped (no entity definition): {skipped}")

    print(f"\n  Total parsed: {len(entities)} entities.")

    print("\n── Step 3: Building text chunks ──────────────────────────")
    chunks = build_chunks(entities)
    print(f"  {len(chunks)} chunks ready for embedding.")

    print("\n── Step 4: Embedding with Voyage AI (voyage-4) ───────────")
    texts = [c["chunk"] for c in chunks]
    embeddings = embed_documents(texts)
    print(f"  {len(embeddings)} embeddings generated.")

    print("\n── Step 5: Upserting into ChromaDB ───────────────────────")
    upsert_chunks(chunks, embeddings)
    print("  ChromaDB upsert complete.")

    print("\n── Step 6: Loading Neo4j graph ───────────────────────────")
    build_graph(entities, manifest["relationships"])
    print("  Neo4j load complete.")

    print("\n✓ Ingestion finished successfully.")


def _parse_raw(raw: dict, filename: str) -> dict | None:
    """Parse a CDM JSON dict without writing to disk."""
    import json
    import tempfile
    from pathlib import Path
    from app.ingestion.parser import parse_entity_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cdm.json", delete=False) as f:
        json.dump(raw, f)
        tmp_path = Path(f.name)

    try:
        return parse_entity_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
