"""Build the Chroma knowledge base from real documents in ``genai/knowledge/``.

Only documents go here (safety guidelines, wadi descriptions, past flood
reports). Numeric risk data is NEVER embedded: it is read live through the SQL
tools. Files whose name starts with ``_`` (templates) are skipped.

Run:  python -m genai.vector_store_setup            # (re)index
      python -m genai.vector_store_setup --reset    # wipe the collection first
"""

import argparse
import hashlib
import logging
import re
from pathlib import Path

import chromadb

from genai.settings import CHROMA_COLLECTION, CHROMA_DIR, KNOWLEDGE_DIR

logger = logging.getLogger("vector_store_setup")

MAX_CHUNK_CHARS = 900


def get_collection(client=None, embedding_function=None):
    client = client or chromadb.PersistentClient(path=CHROMA_DIR)
    kwargs = {"name": CHROMA_COLLECTION, "metadata": {"hnsw:space": "cosine"}}
    if embedding_function is not None:
        kwargs["embedding_function"] = embedding_function
    return client.get_or_create_collection(**kwargs)


def _front_matter(text: str) -> tuple[dict, str]:
    """Tiny `key: value` front-matter parser (between --- lines)."""
    meta: dict = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = parts[2]
    return meta, text.strip()


def chunk_markdown(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[str, str]]:
    """Split by headings, then by paragraphs. Returns (heading, chunk_text)."""
    sections: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in text.splitlines():
        if re.match(r"^#{1,4}\s", line):
            if "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))

    chunks: list[tuple[str, str]] = []
    for head, body in sections:
        current = ""
        for para in re.split(r"\n\s*\n", body):
            if current and len(current) + len(para) > max_chars:
                chunks.append((head, current.strip()))
                current = ""
            current += para + "\n\n"
        if current.strip():
            chunks.append((head, current.strip()))
    return chunks


def load_documents(knowledge_dir: str = KNOWLEDGE_DIR) -> list[dict]:
    root = Path(knowledge_dir)
    items: list[dict] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_") or path.name.lower() == "readme.md":
            continue
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        rel = path.relative_to(root).as_posix()
        for i, (head, chunk) in enumerate(chunk_markdown(body)):
            digest = hashlib.sha1(f"{rel}:{i}:{chunk}".encode("utf-8")).hexdigest()[:16]
            items.append({
                "id": f"{rel}#{i}-{digest}",
                "text": (f"{head}\n{chunk}" if head else chunk),
                "metadata": {
                    "source": rel,
                    "title": meta.get("title", path.stem),
                    "doc_type": meta.get("doc_type", path.parent.name),
                    "language": meta.get("language", ""),
                    "origin": meta.get("origin", ""),
                    "heading": head,
                },
            })
    return items


def build_index(knowledge_dir: str = KNOWLEDGE_DIR, reset: bool = False, client=None,
                embedding_function=None) -> int:
    client = client or chromadb.PersistentClient(path=CHROMA_DIR)
    if reset:
        try:
            client.delete_collection(CHROMA_COLLECTION)
        except Exception:  # collection did not exist
            pass
    collection = get_collection(client, embedding_function)
    items = load_documents(knowledge_dir)
    if not items:
        logger.warning("No documents found in %s", knowledge_dir)
        return 0

    current_ids = {it["id"] for it in items}
    existing = collection.get()["ids"]
    stale = [i for i in existing if i not in current_ids]
    if stale:
        collection.delete(ids=stale)
    collection.upsert(
        ids=[it["id"] for it in items],
        documents=[it["text"] for it in items],
        metadatas=[it["metadata"] for it in items],
    )
    logger.info("Indexed %d chunks from %s", len(items), knowledge_dir)
    return len(items)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    print(f"Indexed {build_index(reset=args.reset)} chunks into '{CHROMA_COLLECTION}' at {CHROMA_DIR}")
